"""JSONL streaming engine for whalecli.

Implements the continuous polling loop for `whalecli stream`.
Emits one JSON object per line to stdout, designed for agent/pipe consumers.

Event types emitted:
  stream_start    — stream begins
  heartbeat       — periodic proof-of-life (even with no whale activity)
  whale_alert     — wallet score >= threshold
  whale_activity  — wallet moved but below threshold
  stream_error    — recoverable API error in a poll cycle
  stream_end      — SIGINT / SIGTERM → clean exit 130

stdout is flushed after each write (critical for pipe consumers).
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from whalecli.alert import process_alerts
from whalecli.config import WhalecliConfig
from whalecli.db import Database
from whalecli.exceptions import NetworkError, WhalecliError
from whalecli.fetchers import get_fetcher
from whalecli.models import Transaction
from whalecli.scorer import load_exchange_addresses, score_wallet


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def emit_event(event: dict[str, Any]) -> None:
    """
    Write a single JSONL event to stdout and flush.

    Never use print() — buffered output breaks pipe consumers.
    """
    sys.stdout.write(json.dumps(event, cls=DecimalEncoder) + "\n")
    sys.stdout.flush()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


async def run_stream(
    chains: list[str],
    interval_seconds: int,
    threshold: int,
    config: WhalecliConfig,
    db: Database,
    hours: int = 1,
) -> None:
    """
    Main stream loop. Runs until cancelled (KeyboardInterrupt → exit 130).

    On each poll cycle:
    1. Fetch tracked wallets for each chain
    2. Fetch transactions for all wallets concurrently
    3. Score all wallets
    4. Emit whale_alert or whale_activity for each wallet result
    5. Process alerts (webhook dispatch) for high-score wallets
    6. Emit heartbeat

    Args:
        chains: List of chain identifiers to stream (e.g. ["ETH", "BTC"])
        interval_seconds: Poll every N seconds
        threshold: Score threshold for whale_alert vs whale_activity
        config: Loaded WhalecliConfig
        db: Open Database connection
        hours: Look-back window per poll (default 1h)
    """
    chain_display = ",".join(chains) if chains else "all"
    cycle = 0
    total_alerts = 0

    emit_event({
        "type": "stream_start",
        "timestamp": _now_iso(),
        "chain": chain_display,
        "interval_secs": interval_seconds,
        "threshold": threshold,
    })

    try:
        while True:
            cycle += 1
            wallets_checked = 0

            try:
                scored_wallets = await _poll_cycle(chains, hours, config, db)
                wallets_checked = len(scored_wallets)

                # First pass: compute all directions for correlation
                directions = {
                    w["address"]: w.get("direction", "neutral")
                    for w in scored_wallets
                }

                for wallet in scored_wallets:
                    score = wallet.get("score", 0)
                    event_type = "whale_alert" if score >= threshold else "whale_activity"
                    emit_event({
                        "type": event_type,
                        "timestamp": _now_iso(),
                        "address": wallet.get("address", ""),
                        "chain": wallet.get("chain", ""),
                        "label": wallet.get("label", ""),
                        "score": score,
                        "score_breakdown": wallet.get("score_breakdown", {}),
                        "direction": wallet.get("direction", "neutral"),
                        "net_flow_usd": wallet.get("net_flow_usd", 0.0),
                        "tx_count_in_window": wallet.get("tx_count", 0),
                        "alert_triggered": score >= threshold,
                        "cycle": cycle,
                    })

                # Process alerts (dedup + webhook) for high-score wallets
                above_threshold = [w for w in scored_wallets if w.get("score", 0) >= threshold]
                if above_threshold:
                    new_alerts = await process_alerts(above_threshold, db, config)
                    total_alerts += len(new_alerts)

            except (WhalecliError, NetworkError) as e:
                emit_event({
                    "type": "stream_error",
                    "timestamp": _now_iso(),
                    "error_code": getattr(e, "error_code", "error"),
                    "message": str(e),
                    "recoverable": True,
                    "cycle": cycle,
                })

            emit_event({
                "type": "heartbeat",
                "timestamp": _now_iso(),
                "cycle": cycle,
                "wallets_checked": wallets_checked,
            })

            await asyncio.sleep(interval_seconds)

    except (KeyboardInterrupt, asyncio.CancelledError):
        emit_event({
            "type": "stream_end",
            "timestamp": _now_iso(),
            "cycles_completed": cycle,
            "total_alerts": total_alerts,
        })
        return  # Caller (CLI) is responsible for sys.exit(130)


async def _poll_cycle(
    chains: list[str],
    hours: int,
    config: WhalecliConfig,
    db: Database,
) -> list[dict[str, Any]]:
    """
    Fetch transactions and score all wallets for one poll cycle.

    Returns list of scored wallet dicts.
    """
    # Determine which chains to poll
    if not chains or chains == ["ALL"]:
        query_chains = ["ETH", "BTC"]
    else:
        query_chains = [c.upper() for c in chains]

    scored: list[dict[str, Any]] = []

    for chain in query_chains:
        wallets = await db.list_wallets(chain=chain)
        if not wallets:
            continue

        fetcher = get_fetcher(chain, config)
        exchange_addrs = load_exchange_addresses(chain)

        # Fetch transactions concurrently for all wallets
        tasks = [
            _fetch_and_score(wallet, hours, fetcher, exchange_addrs, db)
            for wallet in wallets
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue
            if result is not None:
                scored.append(result)

    return scored


async def _fetch_and_score(
    wallet: dict[str, Any],
    hours: int,
    fetcher: Any,
    exchange_addrs: set[str],
    db: Database,
) -> dict[str, Any] | None:
    """Fetch transactions for a single wallet and compute its score."""
    from datetime import timedelta
    now = datetime.now(tz=timezone.utc)
    from_ts = int((now - timedelta(hours=hours)).timestamp())
    to_ts = int(now.timestamp())

    try:
        raw_txns: list[Transaction] = await fetcher.get_transactions(
            wallet["address"], hours
        )
    except Exception:
        raw_txns = []

    # Get 30d baseline
    try:
        avg_flow = await _get_30d_avg(wallet, db)
    except Exception:
        avg_flow = 0.0

    return score_wallet(
        address=wallet["address"],
        chain=wallet["chain"],
        transactions=raw_txns,
        wallet_age_days=0,
        avg_30d_daily_flow_usd=avg_flow,
        exchange_addresses=exchange_addrs,
        all_wallet_directions={},
        scan_hours=hours,
        label=wallet.get("label", ""),
    )


async def _get_30d_avg(wallet: dict[str, Any], db: Database) -> float:
    """Get 30-day average daily flow for velocity baseline."""
    history = await db.get_score_history(wallet["address"], wallet["chain"], days=30)
    if not history:
        return 0.0
    flows = [abs(h.get("net_flow_usd") or 0.0) for h in history]
    return sum(flows) / len(flows) if flows else 0.0
