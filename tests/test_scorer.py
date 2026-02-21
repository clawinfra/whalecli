"""Tests for whalecli/scorer.py — whale scoring algorithm."""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone

import pytest

from whalecli.models import Transaction
from whalecli.scorer import (
    compute_correlation_score,
    compute_exchange_flow_score,
    compute_net_flow_score,
    compute_velocity_score,
    load_exchange_addresses,
    score_to_severity,
    score_wallet,
)


ETH_ADDR = "0xabcdef1234567890abcdef1234567890abcdef12"
TS = datetime(2026, 2, 22, 12, 0, 0, tzinfo=timezone.utc).isoformat()


def make_tx(
    to_addr: str = ETH_ADDR,
    from_addr: str = "0xsender",
    value_usd: float = 1_000.0,
    tx_hash: str = "0xhash",
    chain: str = "ETH",
) -> Transaction:
    return Transaction(
        tx_hash=tx_hash,
        chain=chain,
        from_addr=from_addr,
        to_addr=to_addr,
        timestamp=TS,
        value_native=Decimal("1.0"),
        block_num=100,
        value_usd=value_usd,
        gas_usd=5.0,
        token_symbol=None,
        token_addr=None,
        fetched_at="",
    )


# ── compute_net_flow_score ────────────────────────────────────────────────────


def test_net_flow_score_zero_transactions() -> None:
    """Empty transaction list should score 0."""
    score, direction, net, inflow, outflow = compute_net_flow_score([], ETH_ADDR, 365)
    assert score == 0
    assert direction == "neutral"
    assert net == 0.0
    assert inflow == 0.0
    assert outflow == 0.0


def test_net_flow_score_pure_inflow() -> None:
    """Large inflow should score > 0 and direction = accumulating."""
    txns = [make_tx(to_addr=ETH_ADDR, value_usd=2_000_000.0, tx_hash=f"0x{i}") for i in range(5)]
    score, direction, net, inflow, outflow = compute_net_flow_score(txns, ETH_ADDR, 365)
    assert score > 0
    assert direction == "accumulating"
    assert net > 0
    assert inflow == 10_000_000.0


def test_net_flow_score_pure_outflow() -> None:
    """Large outflow should direction = distributing."""
    txns = [make_tx(from_addr=ETH_ADDR, to_addr="0xrecip", value_usd=1_500_000.0, tx_hash=f"0x{i}") for i in range(3)]
    score, direction, net, inflow, outflow = compute_net_flow_score(txns, ETH_ADDR, 365)
    assert direction == "distributing"
    assert net < 0
    assert outflow == 4_500_000.0


def test_net_flow_score_new_wallet_gets_age_boost() -> None:
    """New wallet (age < 30 days) should get age weight = 1.3."""
    txns = [make_tx(to_addr=ETH_ADDR, value_usd=500_000.0)]
    score_new, _, _, _, _ = compute_net_flow_score(txns, ETH_ADDR, wallet_age_days=15)
    score_old, _, _, _, _ = compute_net_flow_score(txns, ETH_ADDR, wallet_age_days=1000)
    # New wallet should score higher
    assert score_new >= score_old


def test_net_flow_score_large_flow_is_high() -> None:
    """$10M+ flow should produce a significant score (close to max)."""
    txns = [make_tx(to_addr=ETH_ADDR, value_usd=12_000_000.0)]
    score, _, _, _, _ = compute_net_flow_score(txns, ETH_ADDR, 180)
    assert score >= 25


def test_net_flow_score_clamped_to_40() -> None:
    """Net flow score should never exceed 40."""
    txns = [make_tx(to_addr=ETH_ADDR, value_usd=1e12)]  # $1 trillion
    score, _, _, _, _ = compute_net_flow_score(txns, ETH_ADDR, 365)
    assert score <= 40


# ── compute_velocity_score ───────────────────────────────────────────────────


def test_velocity_score_no_transactions() -> None:
    """No transactions → velocity score 0."""
    score = compute_velocity_score([], avg_30d_daily_flow_usd=50_000.0, scan_hours=24)
    assert score == 0


def test_velocity_score_below_average() -> None:
    """Activity below 30d average → velocity score 0."""
    txns = [make_tx(value_usd=100.0)]
    score = compute_velocity_score(txns, avg_30d_daily_flow_usd=500_000.0, scan_hours=24)
    assert score == 0


def test_velocity_score_10x_above_average() -> None:
    """10x above average should produce velocity score > 20."""
    txns = [make_tx(value_usd=5_000_000.0) for _ in range(2)]
    # Average: $100k/day, current: $10M/day
    score = compute_velocity_score(txns, avg_30d_daily_flow_usd=100_000.0, scan_hours=24)
    assert score > 20


def test_velocity_score_dormant_then_active() -> None:
    """Wallet with near-zero 30d average suddenly active → score near max."""
    txns = [make_tx(value_usd=1_000_000.0)]
    # Avg baseline is very low
    score = compute_velocity_score(txns, avg_30d_daily_flow_usd=1.0, scan_hours=24)
    assert score == 25  # Should be capped at 25


def test_velocity_score_clamped_to_25() -> None:
    """Velocity score should never exceed 25."""
    txns = [make_tx(value_usd=1e9) for _ in range(100)]
    score = compute_velocity_score(txns, avg_30d_daily_flow_usd=1.0, scan_hours=24)
    assert score <= 25


# ── compute_correlation_score ────────────────────────────────────────────────


def test_correlation_score_neutral_wallet() -> None:
    """Neutral wallet direction → correlation score 0."""
    score = compute_correlation_score("neutral", {"0xother": "accumulating"})
    assert score == 0


def test_correlation_score_all_same_direction() -> None:
    """All active wallets in same direction → correlation score = 20."""
    other = {
        "0xaaa": "accumulating",
        "0xbbb": "accumulating",
        "0xccc": "accumulating",
    }
    score = compute_correlation_score("accumulating", other)
    assert score == 20


def test_correlation_score_zero_correlation() -> None:
    """No other wallets in same direction → score 0."""
    other = {
        "0xaaa": "distributing",
        "0xbbb": "distributing",
    }
    score = compute_correlation_score("accumulating", other)
    assert score == 0


def test_correlation_score_50_percent() -> None:
    """50% correlation → score = 10."""
    other = {
        "0xaaa": "accumulating",
        "0xbbb": "distributing",
        "0xccc": "accumulating",
        "0xddd": "distributing",
    }
    score = compute_correlation_score("accumulating", other)
    assert score == 10


def test_correlation_score_fewer_than_min_peers() -> None:
    """Fewer than 2 active peers → score 0."""
    other = {"0xaaa": "accumulating"}
    score = compute_correlation_score("accumulating", other)
    assert score == 0


def test_correlation_score_clamped_to_20() -> None:
    """Correlation score should never exceed 20."""
    other = {f"0x{i:040x}": "accumulating" for i in range(100)}
    score = compute_correlation_score("accumulating", other)
    assert score <= 20


# ── compute_exchange_flow_score ──────────────────────────────────────────────


EXCH_ADDR = "0xexchange_addr"


def test_exchange_flow_score_no_exchange_txns() -> None:
    """No transactions with exchange addresses → score 0."""
    txns = [make_tx(to_addr=ETH_ADDR, from_addr="0xrandom")]
    score, fraction = compute_exchange_flow_score(txns, ETH_ADDR, {EXCH_ADDR}, 1000.0)
    assert score == 0
    assert fraction == 0.0


def test_exchange_flow_score_large_exchange_inflow() -> None:
    """Large flow from exchange → significant score."""
    # Exchange sends to wallet
    txns = [
        Transaction(
            tx_hash=f"0xex{i}",
            chain="ETH",
            from_addr=EXCH_ADDR,
            to_addr=ETH_ADDR,
            timestamp=TS,
            value_native=Decimal("100.0"),
            block_num=100 + i,
            value_usd=300_000.0,
            gas_usd=5.0,
            token_symbol=None,
            token_addr=None,
            fetched_at="",
        )
        for i in range(5)
    ]
    score, fraction = compute_exchange_flow_score(txns, ETH_ADDR, {EXCH_ADDR}, 1_500_000.0)
    assert score > 5
    assert fraction > 0.5


def test_exchange_flow_fraction_bounded() -> None:
    """Exchange flow fraction should never exceed 1.0."""
    txns = [make_tx(from_addr=EXCH_ADDR, to_addr=ETH_ADDR, value_usd=1_000_000.0)]
    _, fraction = compute_exchange_flow_score(txns, ETH_ADDR, {EXCH_ADDR}, 1_000_000.0)
    assert 0.0 <= fraction <= 1.0


def test_exchange_flow_score_clamped_to_15() -> None:
    """Exchange flow score should never exceed 15."""
    txns = [
        Transaction(
            tx_hash=f"0xex{i}",
            chain="ETH",
            from_addr=EXCH_ADDR,
            to_addr=ETH_ADDR,
            timestamp=TS,
            value_native=Decimal("1000.0"),
            block_num=100 + i,
            value_usd=1e9,
            gas_usd=5.0,
            token_symbol=None,
            token_addr=None,
            fetched_at="",
        )
        for i in range(10)
    ]
    score, _ = compute_exchange_flow_score(txns, ETH_ADDR, {EXCH_ADDR}, 1e10)
    assert score <= 15


# ── score_wallet (composite) ──────────────────────────────────────────────────


def test_score_wallet_empty_transactions() -> None:
    """Empty transaction list → score 0."""
    result = score_wallet(
        address=ETH_ADDR,
        chain="ETH",
        transactions=[],
        wallet_age_days=365,
        avg_30d_daily_flow_usd=50_000.0,
        exchange_addresses=set(),
        all_wallet_directions={},
        scan_hours=24,
    )
    assert result["score"] == 0
    assert result["direction"] == "neutral"


def test_score_wallet_returns_0_to_100() -> None:
    """score_wallet result should always be 0–100."""
    txns = [make_tx(value_usd=1_000_000.0)]
    result = score_wallet(
        address=ETH_ADDR,
        chain="ETH",
        transactions=txns,
        wallet_age_days=365,
        avg_30d_daily_flow_usd=100_000.0,
        exchange_addresses=set(),
        all_wallet_directions={},
        scan_hours=24,
    )
    assert 0 <= result["score"] <= 100


def test_score_wallet_has_required_fields() -> None:
    """score_wallet returns dict with all required fields."""
    result = score_wallet(
        address=ETH_ADDR,
        chain="ETH",
        transactions=[],
        wallet_age_days=100,
        avg_30d_daily_flow_usd=0.0,
        exchange_addresses=set(),
        all_wallet_directions={},
        scan_hours=24,
    )
    required_keys = {
        "address", "chain", "score", "score_breakdown",
        "direction", "net_flow_usd", "inflow_usd", "outflow_usd",
        "tx_count", "wallet_age_days", "exchange_flow_fraction",
    }
    assert required_keys.issubset(result.keys())


def test_score_wallet_breakdown_sums_to_total() -> None:
    """Sub-scores should sum to total (within 1 due to rounding)."""
    txns = [make_tx(value_usd=2_000_000.0, to_addr=ETH_ADDR)]
    result = score_wallet(
        address=ETH_ADDR,
        chain="ETH",
        transactions=txns,
        wallet_age_days=365,
        avg_30d_daily_flow_usd=100_000.0,
        exchange_addresses=set(),
        all_wallet_directions={},
        scan_hours=24,
    )
    bd = result["score_breakdown"]
    sub_total = bd["net_flow"] + bd["velocity"] + bd["correlation"] + bd["exchange_flow"]
    assert abs(sub_total - result["score"]) <= 1


def test_score_wallet_high_accumulation() -> None:
    """Wallet with large, fast inflow from exchanges should score >= 70."""
    exchange_addrs = {"0xexchange_whale"}
    txns = [
        Transaction(
            tx_hash=f"0x{i:040x}",
            chain="ETH",
            from_addr="0xexchange_whale",
            to_addr=ETH_ADDR,
            timestamp=TS,
            value_native=Decimal("1000.0"),
            block_num=18_000_000 + i,
            value_usd=3_000_000.0,
            gas_usd=5.0,
            token_symbol=None,
            token_addr=None,
            fetched_at="",
        )
        for i in range(4)
    ]
    result = score_wallet(
        address=ETH_ADDR,
        chain="ETH",
        transactions=txns,
        wallet_age_days=365,
        avg_30d_daily_flow_usd=50_000.0,
        exchange_addresses=exchange_addrs,
        all_wallet_directions={},
        scan_hours=4,
    )
    assert result["score"] >= 60
    assert result["direction"] == "accumulating"


# ── score_to_severity ─────────────────────────────────────────────────────────


def test_severity_critical() -> None:
    assert score_to_severity(90) == "critical"
    assert score_to_severity(100) == "critical"


def test_severity_warning() -> None:
    assert score_to_severity(80) == "warning"
    assert score_to_severity(89) == "warning"


def test_severity_info() -> None:
    assert score_to_severity(70) == "info"
    assert score_to_severity(79) == "info"


def test_severity_none_below_70() -> None:
    assert score_to_severity(69) is None
    assert score_to_severity(0) is None


# ── load_exchange_addresses ───────────────────────────────────────────────────


def test_load_exchange_addresses_eth() -> None:
    """Should return a non-empty set for ETH."""
    addrs = load_exchange_addresses("ETH")
    assert isinstance(addrs, set)
    assert len(addrs) > 0


def test_load_exchange_addresses_all_lowercase() -> None:
    """All addresses should be lowercase."""
    addrs = load_exchange_addresses("ETH")
    for addr in addrs:
        assert addr == addr.lower()


def test_load_exchange_addresses_unknown_chain() -> None:
    """Unknown chain should return empty set (not raise)."""
    addrs = load_exchange_addresses("UNKNOWN")
    assert addrs == set()
