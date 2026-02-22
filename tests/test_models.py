"""Tests for whalecli/models.py — data model methods."""

from __future__ import annotations

from whalecli.models import (
    AlertEvent,
    AlertRule,
    ScoreBreakdown,
    ScoreComponent,
    Wallet,
)

# ── Wallet ────────────────────────────────────────────────────────────────────


def test_wallet_short_address_long() -> None:
    """short_address truncates long addresses."""
    w = Wallet(
        address="0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
        chain="ETH",
        label="",
        tags=[],
        added_at="2026-01-01T00:00:00+00:00",
    )
    short = w.short_address()
    assert "..." in short
    assert len(short) < len(w.address)
    assert short.startswith("0xd8da")


def test_wallet_short_address_short() -> None:
    """short_address returns original for short addresses."""
    w = Wallet(
        address="0xshort",
        chain="ETH",
        label="",
        tags=[],
        added_at="2026-01-01T00:00:00+00:00",
    )
    assert w.short_address() == "0xshort"


def test_wallet_display_name_with_label() -> None:
    """display_name returns label when set."""
    w = Wallet(
        address="0xabc",
        chain="ETH",
        label="Whale Fund",
        tags=[],
        added_at="2026-01-01T00:00:00+00:00",
    )
    assert w.display_name() == "Whale Fund"


def test_wallet_display_name_no_label() -> None:
    """display_name returns short_address when no label."""
    w = Wallet(
        address="0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
        chain="ETH",
        label="",
        tags=[],
        added_at="2026-01-01T00:00:00+00:00",
    )
    assert "..." in w.display_name()


# ── ScoreBreakdown.to_dict() ──────────────────────────────────────────────────


def test_score_breakdown_to_dict() -> None:
    """ScoreBreakdown.to_dict() returns correct structure."""
    sb = ScoreBreakdown(
        address="0xtest",
        chain="ETH",
        computed_at="2026-02-22T12:00:00+00:00",
        window_hours=24,
        total=82,
        net_flow=35,
        velocity=20,
        correlation=15,
        exchange_flow=12,
        direction="accumulating",
        net_flow_usd=5_000_000.0,
        inflow_usd=7_000_000.0,
        outflow_usd=2_000_000.0,
        alert_triggered=True,
    )
    d = sb.to_dict()
    assert d["score"] == 82
    assert d["score_breakdown"]["net_flow"] == 35
    assert d["direction"] == "accumulating"
    assert d["net_flow_usd"] == 5_000_000.0
    assert d["alert_triggered"] is True


def test_score_breakdown_to_dict_with_components() -> None:
    """ScoreBreakdown.to_dict() with component list."""
    component = ScoreComponent(
        name="net_flow",
        value=35,
        max_points=40,
        rationale="Large accumulation",
    )
    sb = ScoreBreakdown(
        address="0xtest",
        chain="ETH",
        computed_at="2026-02-22T12:00:00+00:00",
        window_hours=24,
        total=35,
        net_flow=35,
        velocity=0,
        correlation=0,
        exchange_flow=0,
        direction="neutral",
        net_flow_usd=0.0,
        inflow_usd=0.0,
        outflow_usd=0.0,
        components=[component],
    )
    d = sb.to_dict()
    assert "score_breakdown" in d


# ── AlertEvent.to_dict() ──────────────────────────────────────────────────────


def test_alert_event_to_dict_no_breakdown() -> None:
    """AlertEvent.to_dict() without score_breakdown."""
    ae = AlertEvent(
        id="alert_001",
        rule_id="rule_001",
        address="0xtest",
        chain="ETH",
        label="Whale",
        score=85,
        triggered_at="2026-02-22T12:00:00+00:00",
        webhook_sent=True,
        webhook_status=200,
    )
    d = ae.to_dict()
    assert d["id"] == "alert_001"
    assert d["score"] == 85
    assert d["webhook_sent"] is True
    assert "score_breakdown" not in d


def test_alert_event_to_dict_with_breakdown() -> None:
    """AlertEvent.to_dict() with score_breakdown includes it."""
    sb = ScoreBreakdown(
        address="0xtest",
        chain="ETH",
        computed_at="2026-02-22T12:00:00+00:00",
        window_hours=24,
        total=85,
        net_flow=35,
        velocity=25,
        correlation=15,
        exchange_flow=10,
        direction="accumulating",
        net_flow_usd=5_000_000.0,
        inflow_usd=5_000_000.0,
        outflow_usd=0.0,
    )
    ae = AlertEvent(
        id="alert_002",
        rule_id="rule_002",
        address="0xtest",
        chain="ETH",
        label="Big Whale",
        score=85,
        triggered_at="2026-02-22T12:00:00+00:00",
        score_breakdown=sb,
    )
    d = ae.to_dict()
    assert "score_breakdown" in d
    assert d["score_breakdown"]["net_flow"] == 35


# ── AlertRule.to_dict() ───────────────────────────────────────────────────────


def test_alert_rule_to_dict() -> None:
    """AlertRule.to_dict() returns correct structure."""
    rule = AlertRule(
        id="rule_003",
        type="flow",
        value=5_000_000.0,
        window="4h",
        chain="BTC",
        webhook_url="https://hooks.example.com/whale",
        created_at="2026-02-22T00:00:00+00:00",
        active=True,
    )
    d = rule.to_dict()
    assert d["id"] == "rule_003"
    assert d["type"] == "flow"
    assert d["value"] == 5_000_000.0
    assert d["chain"] == "BTC"
    assert d["active"] is True
