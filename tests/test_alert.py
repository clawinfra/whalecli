"""Tests for whalecli/alert.py — alert detection and webhook delivery."""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

from whalecli.alert import (
    build_webhook_payload,
    compute_scan_summary,
    dispatch_webhook,
    flow_passes_threshold,
    process_alerts,
    score_passes_threshold,
)
from whalecli.config import WhalecliConfig
from whalecli.db import Database

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db() -> Database:
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


def make_config(
    score_threshold: int = 70,
    flow_threshold_usd: float = 1_000_000.0,
    window_minutes: int = 60,
    webhook_url: str = "",
) -> WhalecliConfig:
    cfg = WhalecliConfig()
    cfg.alert.score_threshold = score_threshold
    cfg.alert.flow_threshold_usd = flow_threshold_usd
    cfg.alert.window_minutes = window_minutes
    cfg.alert.webhook_url = webhook_url
    return cfg


def make_wallet(
    score: int = 75,
    direction: str = "accumulating",
    net_flow_usd: float = 2_000_000.0,
    address: str = "0xtest_wallet",
    chain: str = "ETH",
    label: str = "Test Whale",
) -> dict[str, Any]:
    return {
        "address": address,
        "chain": chain,
        "label": label,
        "score": score,
        "direction": direction,
        "net_flow_usd": net_flow_usd,
        "tx_count": 5,
        "wallet_age_days": 365,
        "score_breakdown": {
            "net_flow": 35,
            "velocity": 20,
            "correlation": 12,
            "exchange_flow": 8,
        },
        "alert_triggered": False,
    }


# ── score_passes_threshold ────────────────────────────────────────────────────


def test_score_passes_threshold_above() -> None:
    config = make_config(score_threshold=70)
    assert score_passes_threshold(75, config) is True


def test_score_passes_threshold_at_threshold() -> None:
    config = make_config(score_threshold=70)
    assert score_passes_threshold(70, config) is True


def test_score_passes_threshold_below() -> None:
    config = make_config(score_threshold=70)
    assert score_passes_threshold(69, config) is False


def test_flow_passes_threshold_above() -> None:
    config = make_config(flow_threshold_usd=1_000_000.0)
    assert flow_passes_threshold(2_000_000.0, config) is True


def test_flow_passes_threshold_negative_flow() -> None:
    """Negative net flow (outflow) should also trigger if magnitude exceeds threshold."""
    config = make_config(flow_threshold_usd=1_000_000.0)
    assert flow_passes_threshold(-1_500_000.0, config) is True


def test_flow_passes_threshold_below() -> None:
    config = make_config(flow_threshold_usd=1_000_000.0)
    assert flow_passes_threshold(500_000.0, config) is False


# ── process_alerts ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_alerts_above_threshold(db: Database) -> None:
    """Wallet above score threshold → alert generated."""
    config = make_config(score_threshold=70)
    wallets = [make_wallet(score=82)]
    alerts = await process_alerts(wallets, db, config)
    assert len(alerts) == 1
    assert alerts[0]["score"] == 82


@pytest.mark.asyncio
async def test_process_alerts_below_threshold(db: Database) -> None:
    """Wallet below BOTH score and flow threshold → no alert."""
    config = make_config(score_threshold=70, flow_threshold_usd=100_000_000.0)
    wallets = [make_wallet(score=60, net_flow_usd=50_000.0)]
    alerts = await process_alerts(wallets, db, config)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_process_alerts_marks_wallet_alert_triggered(db: Database) -> None:
    """process_alerts should set alert_triggered=True on the wallet dict."""
    config = make_config(score_threshold=70)
    wallet = make_wallet(score=75)
    wallets = [wallet]
    await process_alerts(wallets, db, config)
    assert wallet["alert_triggered"] is True


@pytest.mark.asyncio
async def test_process_alerts_dedup_within_window(db: Database) -> None:
    """Same wallet alerted twice in the same window → only 1 alert generated."""
    config = make_config(score_threshold=70, window_minutes=60)
    wallet = make_wallet(score=80)

    alerts_first = await process_alerts([wallet], db, config)
    assert len(alerts_first) == 1

    # Reset flag and try again
    wallet["alert_triggered"] = False
    alerts_second = await process_alerts([wallet], db, config)
    assert len(alerts_second) == 0  # duplicate suppressed


@pytest.mark.asyncio
async def test_process_alerts_flow_threshold_triggers(db: Database) -> None:
    """Wallet below score threshold but above flow threshold → alert."""
    config = make_config(score_threshold=90, flow_threshold_usd=1_000_000.0)
    wallet = make_wallet(score=65, net_flow_usd=2_500_000.0)
    alerts = await process_alerts([wallet], db, config)
    assert len(alerts) == 1


@pytest.mark.asyncio
async def test_process_alerts_multiple_wallets(db: Database) -> None:
    """Only wallets meeting score threshold generate alerts (flow threshold set very high)."""
    config = make_config(score_threshold=75, flow_threshold_usd=100_000_000.0)
    wallets = [
        make_wallet(score=80, address="0xwallet1"),
        make_wallet(score=60, address="0xwallet2", net_flow_usd=100.0),
        make_wallet(score=90, address="0xwallet3"),
    ]
    alerts = await process_alerts(wallets, db, config)
    assert len(alerts) == 2


@pytest.mark.asyncio
async def test_process_alerts_persists_to_db(db: Database) -> None:
    """process_alerts should persist alerts to the database."""
    config = make_config(score_threshold=70)
    wallets = [make_wallet(score=85)]
    await process_alerts(wallets, db, config)

    db_alerts = await db.list_alerts()
    assert len(db_alerts) == 1
    assert db_alerts[0]["score"] == 85


# ── build_webhook_payload ─────────────────────────────────────────────────────


def test_build_webhook_payload_structure() -> None:
    """build_webhook_payload produces the correct schema."""
    alert = {
        "id": 1,
        "address": "0xtest",
        "chain": "ETH",
        "label": "Whale",
        "score": 88,
        "direction": "accumulating",
        "net_flow_usd": 5_000_000.0,
        "triggered_at": "2026-02-22T12:00:00+00:00",
        "rule_id": "rule_001",
        "score_breakdown": {"net_flow": 35, "velocity": 25, "correlation": 15, "exchange_flow": 13},
    }
    payload = build_webhook_payload(alert)

    assert payload["schema_version"] == "1"
    assert payload["event_type"] == "whale_alert"
    assert payload["wallet"]["address"] == "0xtest"
    assert payload["score"] == 88
    assert "net_flow_usd" in payload
    assert "score_breakdown" in payload


# ── dispatch_webhook ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_webhook_no_url() -> None:
    """dispatch_webhook returns None if no webhook URL configured."""
    config = make_config(webhook_url="")
    alert = {
        "address": "0xtest",
        "chain": "ETH",
        "label": "",
        "score": 80,
        "direction": "neutral",
        "net_flow_usd": 0.0,
        "triggered_at": "2026-02-22T12:00:00+00:00",
        "rule_id": "auto",
    }
    result = await dispatch_webhook(alert, config)
    assert result is None


@pytest.mark.asyncio
async def test_dispatch_webhook_success(respx_mock) -> None:
    """dispatch_webhook returns 200 on successful delivery."""
    import httpx

    config = make_config(webhook_url="https://hooks.example.com/whale")
    alert = {
        "id": 1,
        "address": "0xtest",
        "chain": "ETH",
        "label": "Whale",
        "score": 80,
        "direction": "accumulating",
        "net_flow_usd": 3_000_000.0,
        "triggered_at": "2026-02-22T12:00:00+00:00",
        "rule_id": "auto",
        "score_breakdown": {},
    }

    respx_mock.post("https://hooks.example.com/whale").mock(return_value=httpx.Response(200))

    status = await dispatch_webhook(alert, config)
    assert status == 200


@pytest.mark.asyncio
async def test_dispatch_webhook_timeout_returns_none(respx_mock) -> None:
    """dispatch_webhook returns None on timeout."""
    import httpx

    config = make_config(webhook_url="https://hooks.example.com/whale")
    alert = {
        "id": 1,
        "address": "0xtest",
        "chain": "ETH",
        "label": "",
        "score": 80,
        "direction": "neutral",
        "net_flow_usd": 0.0,
        "triggered_at": "2026-02-22T12:00:00+00:00",
        "rule_id": "auto",
        "score_breakdown": {},
    }

    respx_mock.post("https://hooks.example.com/whale").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    status = await dispatch_webhook(alert, config)
    assert status is None


# ── compute_scan_summary ──────────────────────────────────────────────────────


def test_scan_summary_all_accumulating() -> None:
    """All accumulating → dominant_signal = accumulating."""
    wallets = [make_wallet(direction="accumulating") for _ in range(5)]
    summary = compute_scan_summary(wallets, [])
    assert summary["dominant_signal"] == "accumulating"
    assert summary["accumulating"] == 5


def test_scan_summary_all_distributing() -> None:
    """All distributing → dominant_signal = distributing."""
    wallets = [make_wallet(direction="distributing") for _ in range(3)]
    summary = compute_scan_summary(wallets, [])
    assert summary["dominant_signal"] == "distributing"


def test_scan_summary_mixed() -> None:
    """Equal accumulating and distributing → dominant_signal = mixed."""
    wallets = [
        make_wallet(direction="accumulating"),
        make_wallet(direction="distributing"),
    ]
    summary = compute_scan_summary(wallets, [])
    assert summary["dominant_signal"] == "mixed"


def test_scan_summary_empty() -> None:
    """Empty wallet list → neutral signal."""
    summary = compute_scan_summary([], [])
    assert summary["dominant_signal"] == "neutral"
    assert summary["total_wallets"] == 0


def test_scan_summary_alert_count() -> None:
    """Summary should include alert count."""
    wallets = [make_wallet(score=80)]
    alerts = [{"id": 1}]
    summary = compute_scan_summary(wallets, alerts)
    assert summary["alerts_triggered"] == 1
