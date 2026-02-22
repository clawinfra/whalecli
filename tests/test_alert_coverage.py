"""Additional coverage tests for alert.py."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
import respx

from whalecli.alert import dispatch_webhook, process_alerts
from whalecli.config import WhalecliConfig
from whalecli.db import Database


@pytest_asyncio.fixture(scope="function")
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


def make_config_with_webhook(
    url: str = "https://hooks.example.com/whale",
    secret: str = "",
    score_threshold: int = 70,
    window_minutes: int = 60,
) -> WhalecliConfig:
    cfg = WhalecliConfig()
    cfg.alert.score_threshold = score_threshold
    cfg.alert.flow_threshold_usd = 100_000_000.0  # High so only score triggers
    cfg.alert.window_minutes = window_minutes
    cfg.alert.webhook_url = url
    cfg.alert.webhook_secret = secret
    return cfg


def make_wallet(score: int = 80, address: str = "0xtest") -> dict[str, Any]:
    return {
        "address": address,
        "chain": "ETH",
        "label": "Test",
        "score": score,
        "direction": "accumulating",
        "net_flow_usd": 5_000_000.0,
        "tx_count": 3,
        "wallet_age_days": 100,
        "score_breakdown": {"net_flow": 30, "velocity": 20, "correlation": 15, "exchange_flow": 15},
        "alert_triggered": False,
    }


# ── Dedup window = 0 ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_alerts_dedup_window_zero(db) -> None:
    """window_minutes=0 falls back to DEFAULT dedup window."""
    config = make_config_with_webhook(window_minutes=0)
    wallet = make_wallet(score=80, address="0xdedup_zero")
    alerts = await process_alerts([wallet], db, config)
    assert len(alerts) == 1  # No existing alert → should trigger


# ── Webhook dispatch with HMAC signature ─────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_dispatch_webhook_with_hmac_signature() -> None:
    """dispatch_webhook includes HMAC signature when secret is configured."""
    config = make_config_with_webhook(
        url="https://hooks.example.com/secure",
        secret="my_secret",
    )
    alert = {
        "id": 1,
        "address": "0xtest",
        "chain": "ETH",
        "label": "Whale",
        "score": 85,
        "direction": "accumulating",
        "net_flow_usd": 3_000_000.0,
        "triggered_at": "2026-02-22T12:00:00+00:00",
        "rule_id": "auto",
        "score_breakdown": {},
    }

    # Track request headers
    captured_headers = {}

    def capture_request(request):
        captured_headers.update(dict(request.headers))
        return httpx.Response(200)

    respx.post("https://hooks.example.com/secure").mock(side_effect=capture_request)

    status = await dispatch_webhook(alert, config)

    assert status == 200
    assert "x-whalecli-signature" in {k.lower(): v for k, v in captured_headers.items()}


# ── HTTPError case ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_dispatch_webhook_http_error_returns_none() -> None:
    """dispatch_webhook returns None on HTTPError."""
    config = make_config_with_webhook(url="https://hooks.example.com/error")
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

    respx.post("https://hooks.example.com/error").mock(
        side_effect=httpx.HTTPError("connection reset")
    )

    status = await dispatch_webhook(alert, config)
    assert status is None


# ── process_alerts webhook dispatch path ─────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_process_alerts_dispatches_webhook(db) -> None:
    """process_alerts calls webhook when URL configured."""
    config = make_config_with_webhook(url="https://hooks.example.com/alert")
    wallet = make_wallet(score=85, address="0xwebhook_alert")

    respx.post("https://hooks.example.com/alert").mock(return_value=httpx.Response(200))

    alerts = await process_alerts([wallet], db, config)
    assert len(alerts) == 1
    assert alerts[0]["webhook_sent"] is True
    assert alerts[0]["webhook_status"] == 200


@pytest.mark.asyncio
@respx.mock
async def test_process_alerts_webhook_failure(db) -> None:
    """process_alerts handles webhook delivery failure gracefully."""
    config = make_config_with_webhook(url="https://hooks.example.com/fail")
    wallet = make_wallet(score=85, address="0xwebhook_fail")

    respx.post("https://hooks.example.com/fail").mock(return_value=httpx.Response(500))

    alerts = await process_alerts([wallet], db, config)
    assert len(alerts) == 1
    assert alerts[0]["webhook_sent"] is False
    assert alerts[0]["webhook_status"] == 500
