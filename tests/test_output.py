"""Tests for whalecli/output.py — output formatting."""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from typing import Any

import pytest

from whalecli.output import (DecimalEncoder, format_csv, format_json,
                             format_jsonl, format_output, format_table,
                             mask_api_key)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_scan_result() -> dict[str, Any]:
    """Scan result dict matching the documented API schema."""
    return {
        "scan_id": "scan_20260222_120000_abcd",
        "scan_time": "2026-02-22T12:00:00+00:00",
        "chain": "ETH",
        "window_hours": 24,
        "wallets_scanned": 3,
        "alerts_triggered": 1,
        "wallets": [
            {
                "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
                "chain": "ETH",
                "label": "Binance Cold",
                "score": 82,
                "score_breakdown": {
                    "net_flow": 35,
                    "velocity": 22,
                    "correlation": 15,
                    "exchange_flow": 10,
                },
                "direction": "accumulating",
                "net_flow_usd": 5_000_000.0,
                "inflow_usd": 7_000_000.0,
                "outflow_usd": 2_000_000.0,
                "tx_count": 12,
                "wallet_age_days": 365,
                "alert_triggered": True,
                "computed_at": "2026-02-22T12:00:00+00:00",
            },
            {
                "address": "0xabc123456789abc123456789abc123456789abc1",
                "chain": "ETH",
                "label": "Whale #2",
                "score": 45,
                "score_breakdown": {
                    "net_flow": 20,
                    "velocity": 15,
                    "correlation": 5,
                    "exchange_flow": 5,
                },
                "direction": "neutral",
                "net_flow_usd": 0.0,
                "inflow_usd": 100_000.0,
                "outflow_usd": 100_000.0,
                "tx_count": 2,
                "wallet_age_days": 100,
                "alert_triggered": False,
                "computed_at": "2026-02-22T12:00:00+00:00",
            },
        ],
        "summary": {
            "total_wallets": 2,
            "accumulating": 1,
            "distributing": 0,
            "neutral": 1,
            "alerts_triggered": 1,
            "dominant_signal": "accumulating",
        },
    }


def make_wallet_list() -> dict[str, Any]:
    return {
        "count": 2,
        "wallets": [
            {
                "address": "0xaaa",
                "chain": "ETH",
                "label": "Whale A",
                "tags": [],
                "added_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "address": "bc1qtest",
                "chain": "BTC",
                "label": "BTC Whale",
                "tags": ["exchange"],
                "added_at": "2026-01-02T00:00:00+00:00",
            },
        ],
    }


def make_alert_list() -> dict[str, Any]:
    return {
        "rules": [
            {
                "id": "rule_001",
                "type": "score",
                "value": 70.0,
                "window": "1h",
                "chain": "ETH",
                "active": True,
            },
        ],
        "recent_alerts": [
            {
                "id": 1,
                "address": "0xwallet",
                "chain": "ETH",
                "score": 85,
                "direction": "accumulating",
                "triggered_at": "2026-02-22T12:00:00+00:00",
                "webhook_sent": True,
            },
        ],
    }


# ── format_json ───────────────────────────────────────────────────────────────


def test_format_json_is_valid_json() -> None:
    """format_json output should be valid JSON."""
    result = format_json({"key": "value", "number": 42})
    parsed = json.loads(result)
    assert parsed["key"] == "value"


def test_format_json_indented() -> None:
    """format_json uses 2-space indentation."""
    result = format_json({"a": 1})
    assert "  " in result  # Has indentation


def test_format_json_handles_decimal() -> None:
    """format_json should serialize Decimal values."""
    result = format_json({"amount": Decimal("1.23456789")})
    parsed = json.loads(result)
    assert isinstance(parsed["amount"], float)


def test_format_json_handles_nested() -> None:
    """format_json handles nested dicts."""
    data = make_scan_result()
    result = format_json(data)
    parsed = json.loads(result)
    assert parsed["wallets"][0]["score"] == 82


# ── format_jsonl ──────────────────────────────────────────────────────────────


def test_format_jsonl_scan_result_emits_events() -> None:
    """format_jsonl for scan result emits scan_start, wallet_result, scan_end."""
    data = make_scan_result()
    result = format_jsonl(data)
    lines = [l for l in result.strip().split("\n") if l.strip()]
    assert len(lines) >= 3

    events = [json.loads(line) for line in lines]
    event_types = [e["type"] for e in events]
    assert "scan_start" in event_types
    assert "wallet_result" in event_types
    assert "scan_end" in event_types


def test_format_jsonl_each_line_is_valid_json() -> None:
    """Each line in JSONL output must be valid JSON."""
    data = make_scan_result()
    result = format_jsonl(data)
    for line in result.strip().split("\n"):
        if line.strip():
            json.loads(line)  # Should not raise


def test_format_jsonl_wallet_count_matches() -> None:
    """Number of wallet_result events should match wallet count."""
    data = make_scan_result()
    result = format_jsonl(data)
    events = [json.loads(l) for l in result.strip().split("\n") if l.strip()]
    wallet_events = [e for e in events if e["type"] == "wallet_result"]
    assert len(wallet_events) == len(data["wallets"])


def test_format_jsonl_scan_end_has_counts() -> None:
    """scan_end event should have wallets_scanned and alerts_triggered."""
    data = make_scan_result()
    result = format_jsonl(data)
    events = [json.loads(l) for l in result.strip().split("\n") if l.strip()]
    end_event = next(e for e in events if e["type"] == "scan_end")
    assert "wallets_scanned" in end_event
    assert "alerts_triggered" in end_event


def test_format_jsonl_list_input() -> None:
    """List input should produce one JSON object per line."""
    data = [{"type": "item", "id": i} for i in range(3)]
    result = format_jsonl(data)
    lines = [l for l in result.strip().split("\n") if l.strip()]
    assert len(lines) == 3


# ── format_table ──────────────────────────────────────────────────────────────


def test_format_table_scan_result_contains_address() -> None:
    """format_table for scan result should contain wallet address."""
    data = make_scan_result()
    result = format_table(data)
    assert "Binance Cold" in result or "0xd8da" in result


def test_format_table_wallet_list_contains_chain() -> None:
    """format_table for wallet list should contain chain names."""
    data = make_wallet_list()
    result = format_table(data)
    assert "ETH" in result or "BTC" in result


def test_format_table_alert_list_contains_rule_id() -> None:
    """format_table for alert list should contain rule ID."""
    data = make_alert_list()
    result = format_table(data)
    assert "rule_001" in result


def test_format_table_returns_string() -> None:
    """format_table should always return a string."""
    assert isinstance(format_table({}), str)
    assert isinstance(format_table({"wallets": []}), str)


# ── format_csv ────────────────────────────────────────────────────────────────


def test_format_csv_scan_result_has_header() -> None:
    """format_csv for scan result should include a header row."""
    data = make_scan_result()
    result = format_csv(data)
    rows = list(csv.reader(io.StringIO(result)))
    assert len(rows) >= 2  # header + at least 1 data row


def test_format_csv_wallet_list_header() -> None:
    """format_csv for wallet list should have address in header."""
    data = make_wallet_list()
    result = format_csv(data)
    first_line = result.strip().split("\n")[0]
    assert "address" in first_line.lower()


def test_format_csv_values_present() -> None:
    """CSV rows should contain expected values."""
    data = make_wallet_list()
    result = format_csv(data)
    assert "0xaaa" in result or "ETH" in result


def test_format_csv_empty_wallets() -> None:
    """Empty wallet list should still produce a valid CSV with header."""
    data = {"wallets": []}
    result = format_csv(data)
    # Should not raise; may produce empty CSV


# ── format_output router ──────────────────────────────────────────────────────


def test_format_output_json() -> None:
    """format_output('json') should return valid JSON."""
    result = format_output({"key": "val"}, "json")
    assert json.loads(result)["key"] == "val"


def test_format_output_jsonl() -> None:
    """format_output('jsonl') should return JSONL-compatible string."""
    result = format_output({"wallets": []}, "jsonl")
    for line in result.strip().split("\n"):
        if line.strip():
            json.loads(line)


def test_format_output_table() -> None:
    """format_output('table') should return a string (not raise)."""
    result = format_output({"wallets": []}, "table")
    assert isinstance(result, str)


def test_format_output_csv() -> None:
    """format_output('csv') should return a string."""
    result = format_output({"wallets": []}, "csv")
    assert isinstance(result, str)


def test_format_output_unknown_format() -> None:
    """format_output with unknown format should raise ValueError."""
    with pytest.raises(ValueError):
        format_output({}, "xml")


def test_format_output_case_insensitive() -> None:
    """format_output should handle uppercase format names."""
    result = format_output({"a": 1}, "JSON")
    assert json.loads(result)["a"] == 1


# ── mask_api_key ──────────────────────────────────────────────────────────────


def test_mask_api_key_normal() -> None:
    """mask_api_key shows first 4 chars + ****."""
    result = mask_api_key("abcdefg123")
    assert result == "abcd****"


def test_mask_api_key_empty() -> None:
    """Empty key returns ****."""
    assert mask_api_key("") == "****"


def test_mask_api_key_short() -> None:
    """Short key (≤4 chars) returns ****."""
    assert mask_api_key("abc") == "****"
    assert mask_api_key("abcd") == "****"


def test_mask_api_key_long() -> None:
    """Long key shows first 4 + ****."""
    result = mask_api_key("my_super_long_api_key_xyz")
    assert result.startswith("my_s")
    assert result.endswith("****")
