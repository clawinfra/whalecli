"""Whale scoring algorithm (0–100).

Composite score across four dimensions:
  1. Net Flow Score    (0–40 pts): Net USD movement magnitude + wallet age weight
  2. Velocity Score   (0–25 pts): Current volume vs 30-day average
  3. Correlation Score (0–20 pts): Coordination with other tracked wallets
  4. Exchange Flow    (0–15 pts): Movement through known exchange addresses

All scoring functions are pure — no I/O, no side effects.

References:
  docs/ARCHITECTURE.md — Whale Scoring Algorithm section
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from whalecli.models import Transaction

# ── Data files ────────────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent / "data"

# Cache for exchange addresses loaded from JSON
_exchange_addr_cache: dict[str, set[str]] = {}


def load_exchange_addresses(chain: str) -> set[str]:
    """
    Load exchange addresses for a chain from the bundled JSON registry.

    Returns a set of lowercase address strings.
    """
    chain_upper = chain.upper()

    if chain_upper in _exchange_addr_cache:
        return _exchange_addr_cache[chain_upper]

    json_path = _DATA_DIR / "exchange_addresses.json"
    if not json_path.exists():
        return set()

    with open(json_path) as f:
        data: dict[str, Any] = json.load(f)

    chain_data = data.get(chain_upper, {})
    addrs: set[str] = set()
    for exchange_addrs in chain_data.values():
        for addr in exchange_addrs:
            addrs.add(addr.lower())

    _exchange_addr_cache[chain_upper] = addrs
    return addrs


# ── Scale factors (calibrated so $10M flow in 24h ≈ 35 pts) ─────────────────
_NET_FLOW_SCALE = (
    3.5  # log10($10M) = 7  → 7 * 3.5 * age_weight = ~24; at age_weight=1.3 → 31.8; target 35 pts
)
_VELOCITY_SCALE = 8.3  # log2(20x) = 4.32 → 4.32 * 8.3 ≈ 35.8, capped at 25


# ── Component 1: Net Flow Score ───────────────────────────────────────────────


def compute_net_flow_score(
    transactions: list[Transaction],
    wallet_address: str,
    wallet_age_days: int,
) -> tuple[int, str, float, float, float]:
    """
    Compute net flow sub-score (0–40 pts).

    Args:
        transactions: Transactions in the scan window for this wallet.
        wallet_address: The wallet being scored (lowercase).
        wallet_age_days: Age of wallet in days.

    Returns:
        (score, direction, net_flow_usd, inflow_usd, outflow_usd)
        direction: "accumulating" | "distributing" | "neutral"
    """
    addr_lower = wallet_address.lower()

    inflow_usd = 0.0
    outflow_usd = 0.0

    for tx in transactions:
        usd = tx.value_usd or 0.0
        # Inflow: wallet is the recipient
        if tx.to_addr.lower() == addr_lower:
            inflow_usd += usd
        # Outflow: wallet is the sender
        if tx.from_addr.lower() == addr_lower:
            outflow_usd += usd

    net_flow_usd = inflow_usd - outflow_usd
    magnitude = abs(net_flow_usd)

    # Age-based weight
    if wallet_age_days < 30:
        age_weight = 1.3  # New wallets — higher signal
    elif wallet_age_days < 180:
        age_weight = 1.1
    elif wallet_age_days < 730:
        age_weight = 1.0
    else:
        age_weight = 0.9  # Old cold wallets — lower noise

    if magnitude < 1.0:
        raw_score = 0.0
    else:
        raw_score = math.log10(magnitude) * age_weight * _NET_FLOW_SCALE

    score = max(0, min(40, round(raw_score)))

    if net_flow_usd > 100:
        direction = "accumulating"
    elif net_flow_usd < -100:
        direction = "distributing"
    else:
        direction = "neutral"

    return score, direction, net_flow_usd, inflow_usd, outflow_usd


# ── Component 2: Velocity Score ───────────────────────────────────────────────

_VELOCITY_BASELINE_USD = 50_000.0  # fallback if no 30d history


def compute_velocity_score(
    transactions: list[Transaction],
    avg_30d_daily_flow_usd: float,
    scan_hours: int,
) -> int:
    """
    Compute velocity sub-score (0–25 pts).

    Measures how much faster than baseline this wallet is moving.

    Args:
        transactions: Transactions in the scan window.
        avg_30d_daily_flow_usd: Average daily USD volume over past 30 days.
        scan_hours: Window size (for daily normalisation).

    Returns:
        Score 0–25.
    """
    if scan_hours <= 0:
        return 0

    recent_volume_usd = sum(abs(tx.value_usd or 0.0) for tx in transactions)

    # Normalise to a daily equivalent
    days_fraction = scan_hours / 24.0
    recent_daily_equivalent = recent_volume_usd / max(days_fraction, 0.001)

    # Baseline: 30d average or fixed fallback
    baseline = avg_30d_daily_flow_usd if avg_30d_daily_flow_usd > 0 else _VELOCITY_BASELINE_USD

    velocity_ratio = recent_daily_equivalent / max(baseline, 1.0)

    if velocity_ratio < 1.0:
        return 0  # Below average = no velocity signal

    raw_score = math.log2(velocity_ratio) * _VELOCITY_SCALE
    return max(0, min(25, round(raw_score)))


# ── Component 3: Correlation Score ────────────────────────────────────────────

_CORRELATION_MIN_PEERS = 2  # Need at least 2 peers for correlation to be meaningful


def compute_correlation_score(
    wallet_direction: str,
    all_wallet_directions: dict[str, str],
) -> int:
    """
    Compute correlation sub-score (0–20 pts).

    Measures whether other tracked wallets are moving in the same direction.

    Args:
        wallet_direction: "accumulating" | "distributing" | "neutral"
        all_wallet_directions: {address: direction} for ALL other tracked wallets.

    Returns:
        Score 0–20.
    """
    if wallet_direction == "neutral":
        return 0

    # Count active peers (non-neutral)
    active_peers = {addr: d for addr, d in all_wallet_directions.items() if d != "neutral"}
    total_active = len(active_peers)

    if total_active < _CORRELATION_MIN_PEERS:
        return 0

    same_direction_count = sum(1 for d in active_peers.values() if d == wallet_direction)

    correlation_ratio = same_direction_count / total_active
    return max(0, min(20, round(correlation_ratio * 20)))


# ── Component 4: Exchange Flow Score ─────────────────────────────────────────


def compute_exchange_flow_score(
    transactions: list[Transaction],
    wallet_address: str,
    exchange_addresses: set[str],
    net_flow_usd: float,
) -> tuple[int, float]:
    """
    Compute exchange flow sub-score (0–15 pts).

    Args:
        transactions: Transactions in the scan window.
        wallet_address: The wallet being scored.
        exchange_addresses: Set of known exchange addresses (lowercase).
        net_flow_usd: Net flow already computed (for direction bonus).

    Returns:
        (score, exchange_flow_fraction)
        exchange_flow_fraction: 0.0–1.0 — what fraction of total volume is exchange-related
    """
    addr_lower = wallet_address.lower()

    exchange_inflow = 0.0  # wallet receives from exchange (accumulating)
    exchange_outflow = 0.0  # wallet sends to exchange (distributing)
    total_volume = 0.0

    for tx in transactions:
        usd = abs(tx.value_usd or 0.0)
        total_volume += usd
        from_lower = tx.from_addr.lower()
        to_lower = tx.to_addr.lower()

        if from_lower in exchange_addresses and to_lower == addr_lower:
            exchange_inflow += usd  # From exchange → wallet = accumulating signal
        elif from_lower == addr_lower and to_lower in exchange_addresses:
            exchange_outflow += usd  # From wallet → exchange = distributing signal

    signal_value = exchange_inflow + exchange_outflow
    exchange_flow_fraction = signal_value / max(total_volume, 1.0)

    if signal_value < 1.0:
        return 0, 0.0

    base_score = min(12.0, math.log10(max(signal_value, 1.0)) * 5.0)

    # Direction bonus: exchange flow confirms net flow direction
    exchange_net = exchange_inflow - exchange_outflow
    direction_matches = (exchange_net > 0) == (net_flow_usd > 0) if abs(exchange_net) > 0 else False
    direction_bonus = 3.0 if direction_matches else 0.0

    score = max(0, min(15, round(base_score + direction_bonus)))
    return score, min(exchange_flow_fraction, 1.0)


# ── Composite scorer ──────────────────────────────────────────────────────────


def score_wallet(
    address: str,
    chain: str,
    transactions: list[Transaction],
    wallet_age_days: int,
    avg_30d_daily_flow_usd: float,
    exchange_addresses: set[str],
    all_wallet_directions: dict[str, str],
    scan_hours: int = 24,
    label: str = "",
) -> dict[str, Any]:
    """
    Compute full whale score for a wallet.

    Args:
        address: Wallet address
        chain: Chain identifier
        transactions: Transactions in the scan window
        wallet_age_days: Wallet age in days
        avg_30d_daily_flow_usd: 30-day average daily USD volume
        exchange_addresses: Set of known exchange addresses
        all_wallet_directions: Other wallets' directions (for correlation)
        scan_hours: Scan window in hours
        label: Optional human-readable wallet label

    Returns:
        Dict matching the scan result wallet schema from docs/API.md
    """
    computed_at = datetime.now(tz=timezone.utc).isoformat()

    # Component 1: Net Flow
    nf_score, direction, net_flow_usd, inflow_usd, outflow_usd = compute_net_flow_score(
        transactions, address, wallet_age_days
    )

    # Component 2: Velocity
    vel_score = compute_velocity_score(transactions, avg_30d_daily_flow_usd, scan_hours)

    # Component 3: Correlation
    corr_score = compute_correlation_score(direction, all_wallet_directions)

    # Component 4: Exchange Flow
    exch_score, exchange_flow_fraction = compute_exchange_flow_score(
        transactions, address, exchange_addresses, net_flow_usd
    )

    total = max(0, min(100, nf_score + vel_score + corr_score + exch_score))

    return {
        "address": address,
        "chain": chain,
        "label": label,
        "computed_at": computed_at,
        "window_hours": scan_hours,
        "score": total,
        "score_breakdown": {
            "net_flow": nf_score,
            "velocity": vel_score,
            "correlation": corr_score,
            "exchange_flow": exch_score,
        },
        "direction": direction,
        "net_flow_usd": net_flow_usd,
        "inflow_usd": inflow_usd,
        "outflow_usd": outflow_usd,
        "tx_count": len(transactions),
        "wallet_age_days": wallet_age_days,
        "exchange_flow_fraction": exchange_flow_fraction,
        "alert_triggered": False,  # Set by alert.py after threshold check
        "last_activity": transactions[0].timestamp if transactions else None,
    }


def score_to_severity(score: int) -> str | None:
    """
    Map score to severity label.

    Returns:
        "info" (70–79), "warning" (80–89), "critical" (90+), or None (<70)
    """
    if score >= 90:
        return "critical"
    elif score >= 80:
        return "warning"
    elif score >= 70:
        return "info"
    return None
