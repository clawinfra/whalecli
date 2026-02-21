"""Alert detection and webhook notifications."""

import httpx
from dataclasses import dataclass
from typing import List
from datetime import datetime
from whalecli.config import AlertConfig
from whalecli.scorer import ScoreResult


@dataclass
class Alert:
    """Alert data model."""
    wallet_address: str
    score: int
    flow_usd: float
    triggered_at: datetime
    details: str


def check_alerts(scan_results: List[ScoreResult], config: AlertConfig) -> List[Alert]:
    """Check if any wallets meet alert thresholds.

    Args:
        scan_results: List of scan results with scores.
        config: Alert configuration.

    Returns:
        List of triggered alerts.
    """
    # TODO: Implement in Builder phase
    alerts = []

    for result in scan_results:
        # Check score threshold
        if config.score_threshold and result.final_score >= config.score_threshold:
            alerts.append(Alert(
                wallet_address="",  # Will be filled in
                score=result.final_score,
                flow_usd=result.net_flow_usd,
                triggered_at=datetime.now(),
                details=f"Score threshold met: {result.final_score} >= {config.score_threshold}"
            ))

        # Check flow threshold
        if config.flow_threshold_usd and abs(result.net_flow_usd) >= config.flow_threshold_usd:
            alerts.append(Alert(
                wallet_address="",  # Will be filled in
                score=result.final_score,
                flow_usd=result.net_flow_usd,
                triggered_at=datetime.now(),
                details=f"Flow threshold met: ${abs(result.net_flow_usd):,.0f} >= ${config.flow_threshold_usd:,.0f}"
            ))

    return alerts


def trigger_webhook(alert: Alert, webhook_url: str):
    """Send alert to webhook URL.

    Args:
        alert: Alert to send.
        webhook_url: Webhook URL.

    Raises:
        httpx.HTTPError: If webhook request fails.
    """
    # TODO: Implement in Builder phase
    if not webhook_url:
        return

    payload = format_alert_message(alert)

    try:
        response = httpx.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as e:
        # Log error but don't raise (webhook failures shouldn't crash the scan)
        print(f"Webhook failed: {e}")


def format_alert_message(alert: Alert) -> dict:
    """Format alert as a JSON payload.

    Args:
        alert: Alert to format.

    Returns:
        JSON-serializable dict.
    """
    # TODO: Implement in Builder phase
    return {
        "wallet_address": alert.wallet_address,
        "score": alert.score,
        "flow_usd": alert.flow_usd,
        "triggered_at": alert.triggered_at.isoformat(),
        "details": alert.details
    }
