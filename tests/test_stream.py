"""Tests for whalecli/stream.py — JSONL streaming engine."""

from __future__ import annotations

import asyncio
import json
import sys
from decimal import Decimal
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from whalecli.config import WhalecliConfig
from whalecli.db import Database
from whalecli.stream import emit_event, run_stream


@pytest.fixture
def config() -> WhalecliConfig:
    cfg = WhalecliConfig()
    cfg.database.path = ":memory:"
    return cfg


# ── emit_event ────────────────────────────────────────────────────────────────


def test_emit_event_writes_jsonl(capsys) -> None:
    """emit_event writes a single JSON line to stdout."""
    emit_event({"type": "test", "value": 42})
    captured = capsys.readouterr()
    assert captured.out.strip() != ""
    parsed = json.loads(captured.out.strip())
    assert parsed["type"] == "test"
    assert parsed["value"] == 42


def test_emit_event_handles_decimal(capsys) -> None:
    """emit_event handles Decimal values."""
    emit_event({"amount": Decimal("1.5")})
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert parsed["amount"] == 1.5


def test_emit_event_flushes_immediately(capsys) -> None:
    """emit_event should flush stdout after writing."""
    emit_event({"type": "flush_test"})
    captured = capsys.readouterr()
    assert "flush_test" in captured.out


def test_emit_event_newline_terminated(capsys) -> None:
    """emit_event should append a newline."""
    emit_event({"x": 1})
    captured = capsys.readouterr()
    assert captured.out.endswith("\n")


# ── run_stream ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_stream_emits_stream_start(capsys) -> None:
    """run_stream should emit stream_start as first event."""
    config = WhalecliConfig()
    config.database.path = ":memory:"

    with patch("whalecli.stream._poll_cycle", new=AsyncMock(return_value=[])):
        task = asyncio.create_task(
            run_stream(
                chains=["ETH"],
                interval_seconds=1000,  # Long interval so it stops after one heartbeat
                threshold=70,
                config=config,
                db=_make_mock_db(),
                hours=1,
            )
        )
        # Give the stream time to emit stream_start and first heartbeat
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    captured = capsys.readouterr()
    lines = [l for l in captured.out.strip().split("\n") if l.strip()]
    assert len(lines) >= 1

    first_event = json.loads(lines[0])
    assert first_event["type"] == "stream_start"


@pytest.mark.asyncio
async def test_run_stream_emits_heartbeat(capsys) -> None:
    """run_stream should emit heartbeat after each poll cycle."""
    config = WhalecliConfig()
    config.database.path = ":memory:"

    with patch("whalecli.stream._poll_cycle", new=AsyncMock(return_value=[])):
        task = asyncio.create_task(
            run_stream(
                chains=["ETH"],
                interval_seconds=0,  # No sleep between cycles
                threshold=70,
                config=config,
                db=_make_mock_db(),
                hours=1,
            )
        )
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    captured = capsys.readouterr()
    lines = [l for l in captured.out.strip().split("\n") if l.strip()]
    events = [json.loads(l) for l in lines]
    event_types = [e["type"] for e in events]
    assert "heartbeat" in event_types


@pytest.mark.asyncio
async def test_run_stream_emits_stream_end(capsys) -> None:
    """run_stream should emit stream_end when cancelled."""
    config = WhalecliConfig()
    config.database.path = ":memory:"

    with patch("whalecli.stream._poll_cycle", new=AsyncMock(return_value=[])):
        task = asyncio.create_task(
            run_stream(
                chains=["ETH"],
                interval_seconds=1000,
                threshold=70,
                config=config,
                db=_make_mock_db(),
                hours=1,
            )
        )
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    captured = capsys.readouterr()
    lines = [l for l in captured.out.strip().split("\n") if l.strip()]
    events = [json.loads(l) for l in lines]
    event_types = [e["type"] for e in events]
    # stream_end is emitted on cancellation
    assert "stream_end" in event_types


@pytest.mark.asyncio
async def test_run_stream_emits_whale_alert_above_threshold(capsys) -> None:
    """Wallet above threshold should produce whale_alert event."""
    config = WhalecliConfig()
    config.database.path = ":memory:"

    high_score_wallet = {
        "address": "0xtest_whale",
        "chain": "ETH",
        "label": "Test",
        "score": 90,
        "score_breakdown": {"net_flow": 35, "velocity": 25, "correlation": 15, "exchange_flow": 15},
        "direction": "accumulating",
        "net_flow_usd": 10_000_000.0,
        "tx_count": 5,
        "wallet_age_days": 365,
        "exchange_flow_fraction": 0.5,
        "alert_triggered": False,
        "last_activity": None,
        "computed_at": "2026-02-22T12:00:00+00:00",
        "window_hours": 1,
        "inflow_usd": 10_000_000.0,
        "outflow_usd": 0.0,
    }

    with patch("whalecli.stream._poll_cycle", new=AsyncMock(return_value=[high_score_wallet])):
        with patch("whalecli.alert.process_alerts", new=AsyncMock(return_value=[])):
            task = asyncio.create_task(
                run_stream(
                    chains=["ETH"],
                    interval_seconds=1000,
                    threshold=70,
                    config=config,
                    db=_make_mock_db(),
                    hours=1,
                )
            )
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    captured = capsys.readouterr()
    lines = [l for l in captured.out.strip().split("\n") if l.strip()]
    events = [json.loads(l) for l in lines]
    alert_events = [e for e in events if e["type"] == "whale_alert"]
    assert len(alert_events) >= 1
    assert alert_events[0]["score"] == 90


@pytest.mark.asyncio
async def test_run_stream_emits_whale_activity_below_threshold(capsys) -> None:
    """Wallet below threshold should produce whale_activity event, not whale_alert."""
    config = WhalecliConfig()
    config.database.path = ":memory:"

    low_score_wallet = {
        "address": "0xtest_wallet",
        "chain": "ETH",
        "label": "Test",
        "score": 50,
        "score_breakdown": {"net_flow": 20, "velocity": 15, "correlation": 10, "exchange_flow": 5},
        "direction": "neutral",
        "net_flow_usd": 100_000.0,
        "tx_count": 2,
        "wallet_age_days": 365,
        "exchange_flow_fraction": 0.1,
        "alert_triggered": False,
        "last_activity": None,
        "computed_at": "2026-02-22T12:00:00+00:00",
        "window_hours": 1,
        "inflow_usd": 100_000.0,
        "outflow_usd": 0.0,
    }

    with patch("whalecli.stream._poll_cycle", new=AsyncMock(return_value=[low_score_wallet])):
        task = asyncio.create_task(
            run_stream(
                chains=["ETH"],
                interval_seconds=1000,
                threshold=70,
                config=config,
                db=_make_mock_db(),
                hours=1,
            )
        )
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    captured = capsys.readouterr()
    lines = [l for l in captured.out.strip().split("\n") if l.strip()]
    events = [json.loads(l) for l in lines]
    activity_events = [e for e in events if e["type"] == "whale_activity"]
    assert len(activity_events) >= 1
    assert activity_events[0]["score"] == 50


def _make_mock_db() -> MagicMock:
    """Create a mock database with async methods."""
    db = MagicMock(spec=Database)
    db.list_wallets = AsyncMock(return_value=[])
    db.get_score_history = AsyncMock(return_value=[])
    db.save_score = AsyncMock()
    db.save_alert = AsyncMock(return_value={"id": 1})
    db.is_duplicate_alert = AsyncMock(return_value=False)
    db.update_alert_webhook = AsyncMock()
    return db
