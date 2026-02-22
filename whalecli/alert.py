"""Alert detection, deduplication, and webhook delivery.

Processes scored wallet results against configured thresholds.
Deduplicates alerts within configurable windows.
Dispatches webhook payloads for critical events.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

import httpx

from whalecli.config import WhalecliConfig
from whalecli.db import Database
from whalecli.scorer import score_to_severity

# Default dedup window in seconds (1 hour)
_DEFAULT_DEDUP_WINDOW_SECS = 3600

WEBHOOK_SCHEMA_VERSION = "1"


def score_passes_threshold(score: int, config: WhalecliConfig) -> bool:
    """Return True if the score meets the configured alert threshold."""
    return score >= config.alert.score_threshold


def flow_passes_threshold(net_flow_usd: float, config: WhalecliConfig) -> bool:
    """Return True if the absolute net flow meets the USD threshold."""
    return abs(net_flow_usd) >= config.alert.flow_threshold_usd


async def process_alerts(
    scored_wallets: list[dict[str, Any]],
    db: Database,
    config: WhalecliConfig,
    scan_window_hours: int = 24,
) -> list[dict[str, Any]]:
    """
    Filter scored wallets into alerts, deduplicate, persist, and dispatch webhooks.

    Args:
        scored_wallets: List of wallet score dicts (from scorer.py)
        db: Open Database connection
        config: Loaded config with alert thresholds and webhook settings
        scan_window_hours: Scan window (informational)

    Returns:
        List of new, non-duplicate alert dicts that were persisted.
    """
    dedup_window = config.alert.window_minutes * 60  # minutes → seconds
    if dedup_window <= 0:
        dedup_window = _DEFAULT_DEDUP_WINDOW_SECS

    new_alerts: list[dict[str, Any]] = []

    for wallet in scored_wallets:
        score = wallet.get("score", 0)
        net_flow_usd = wallet.get("net_flow_usd", 0.0)
        address = wallet.get("address", "")
        chain = wallet.get("chain", "ETH")

        # Check if score OR flow threshold met
        score_triggered = score_passes_threshold(score, config)
        flow_triggered = flow_passes_threshold(net_flow_usd, config)

        if not score_triggered and not flow_triggered:
            continue

        # Dedup check
        is_dup = await db.is_duplicate_alert(address, chain, dedup_window)
        if is_dup:
            continue

        severity = score_to_severity(score)
        triggered_at = datetime.now(tz=UTC).isoformat()

        alert_data = {
            "address": address,
            "chain": chain,
            "label": wallet.get("label", ""),
            "score": score,
            "direction": wallet.get("direction", "neutral"),
            "net_flow_usd": net_flow_usd,
            "triggered_at": triggered_at,
            "rule_id": "auto",
            "score_breakdown": wallet.get("score_breakdown", {}),
            "severity": severity,
            "tx_count": wallet.get("tx_count", 0),
            "wallet_age_days": wallet.get("wallet_age_days", 0),
        }

        # Persist alert to DB
        saved = await db.save_alert(alert_data)
        alert_data["id"] = saved.get("id")

        # Dispatch webhook if configured
        webhook_sent = False
        webhook_status: int | None = None
        if config.alert.webhook_url:
            status = await dispatch_webhook(alert_data, config)
            webhook_sent = status is not None and 200 <= status < 300
            webhook_status = status
            if alert_data.get("id"):
                await db.update_alert_webhook(alert_data["id"], webhook_sent, webhook_status)

        alert_data["webhook_sent"] = webhook_sent
        alert_data["webhook_status"] = webhook_status

        # Mark the original wallet result as alert-triggered
        wallet["alert_triggered"] = True

        new_alerts.append(alert_data)

    return new_alerts


async def dispatch_webhook(
    alert_data: dict[str, Any],
    config: WhalecliConfig,
) -> int | None:
    """
    Send alert payload to webhook URL via HTTP POST.

    Returns HTTP status code, or None if delivery failed.
    """
    if not config.alert.webhook_url:
        return None

    payload = build_webhook_payload(alert_data)
    body = json.dumps(payload).encode()

    headers: dict[str, str] = {"Content-Type": "application/json"}

    # HMAC signature if secret configured
    if config.alert.webhook_secret:
        sig = hmac.new(
            config.alert.webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        headers["X-Whalecli-Signature"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                config.alert.webhook_url,
                content=body,
                headers=headers,
            )
            return resp.status_code
    except httpx.TimeoutException:
        return None
    except httpx.HTTPError:
        return None


def build_webhook_payload(alert_data: dict[str, Any]) -> dict[str, Any]:
    """
    Build the webhook JSON payload matching the documented schema.

    Schema from docs/API.md — Webhook Payload Schema.
    """
    return {
        "schema_version": WEBHOOK_SCHEMA_VERSION,
        "event_type": "whale_alert",
        "triggered_at": alert_data.get("triggered_at", ""),
        "rule": {
            "id": alert_data.get("rule_id", "auto"),
            "type": "score",
            "value": alert_data.get("score", 0),
        },
        "wallet": {
            "address": alert_data.get("address", ""),
            "chain": alert_data.get("chain", ""),
            "label": alert_data.get("label", ""),
        },
        "score": alert_data.get("score", 0),
        "score_breakdown": alert_data.get("score_breakdown", {}),
        "direction": alert_data.get("direction", "neutral"),
        "net_flow_usd": alert_data.get("net_flow_usd", 0.0),
        "alert_id": f"alert_{alert_data.get('id', 'unknown')}",
    }


def compute_scan_summary(
    scored_wallets: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compute the summary section of a scan result.

    Returns:
        Summary dict with dominant_signal, totals, etc.
    """
    accumulating = sum(1 for w in scored_wallets if w.get("direction") == "accumulating")
    distributing = sum(1 for w in scored_wallets if w.get("direction") == "distributing")

    total = len(scored_wallets)
    if total == 0:
        dominant_signal = "neutral"
    elif accumulating > distributing:
        dominant_signal = "accumulating"
    elif distributing > accumulating:
        dominant_signal = "distributing"
    else:
        dominant_signal = "mixed"

    return {
        "total_wallets": total,
        "accumulating": accumulating,
        "distributing": distributing,
        "neutral": total - accumulating - distributing,
        "alerts_triggered": len(alerts),
        "dominant_signal": dominant_signal,
    }
