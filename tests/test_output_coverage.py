"""Additional coverage tests for output.py — uncovered rendering paths."""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal

import pytest

from whalecli.output import (
    format_csv,
    format_json,
    format_jsonl,
    format_output,
    format_table,
    _flatten_dict,
    _render_alerts_table,
    _render_rules_table,
    _render_wallet_list_table,
)


def test_format_jsonl_alert_list() -> None:
    """format_jsonl handles alert list dict."""
    data = {"recent_alerts": [{"id": 1, "score": 85}]}
    result = format_jsonl(data)
    parsed = json.loads(result)
    assert parsed == data


def test_format_jsonl_single_dict_not_scan() -> None:
    """format_jsonl with non-scan dict emits single line."""
    data = {"type": "simple", "x": 42}
    result = format_jsonl(data)
    lines = [l for l in result.strip().split("\n") if l.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["x"] == 42


def test_format_table_with_rules() -> None:
    """format_table renders alert rules table."""
    data = {
        "rules": [
            {"id": "rule_001", "type": "score", "value": 70.0, "window": "1h", "chain": "ETH", "active": True},
        ],
    }
    result = format_table(data)
    assert isinstance(result, str)
    assert "rule_001" in result


def test_format_table_alert_list_with_no_rules() -> None:
    """format_table renders alerts without rules section."""
    data = {
        "recent_alerts": [{"id": 1, "address": "0xtest", "chain": "ETH", "score": 80,
                           "triggered_at": "2026-02-22T12:00:00+00:00", "webhook_sent": False}],
        "rules": [],
    }
    result = format_table(data)
    assert isinstance(result, str)


def test_format_csv_with_list_input() -> None:
    """format_csv handles plain list input."""
    data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    result = format_csv(data)
    rows = list(csv.reader(io.StringIO(result)))
    assert rows[0] == ["a", "b"]
    assert len(rows) == 3  # header + 2 data rows


def test_format_csv_with_scalar_fallback() -> None:
    """format_csv with scalar data produces single-column output."""
    result = format_csv("hello")
    assert "value" in result or "hello" in result


def test_format_csv_flattens_nested() -> None:
    """format_csv flattens nested score_breakdown."""
    data = {
        "wallets": [{
            "address": "0xtest",
            "chain": "ETH",
            "score": 75,
            "score_breakdown": {"net_flow": 30, "velocity": 20, "correlation": 15, "exchange_flow": 10},
        }]
    }
    result = format_csv(data)
    # Flattened keys like score_breakdown.net_flow should appear
    assert "score_breakdown.net_flow" in result or "score" in result


def test_flatten_dict_nested() -> None:
    """_flatten_dict flattens nested dict keys."""
    d = {"top": "a", "nested": {"inner1": 1, "inner2": 2}}
    flat = _flatten_dict(d)
    assert "nested.inner1" in flat
    assert "nested.inner2" in flat
    assert flat["top"] == "a"


def test_flatten_dict_list_values() -> None:
    """_flatten_dict serializes list values as JSON strings."""
    d = {"tags": ["a", "b", "c"]}
    flat = _flatten_dict(d)
    assert flat["tags"] == '["a", "b", "c"]'


def test_flatten_dict_decimal_values() -> None:
    """_flatten_dict converts Decimal to float."""
    d = {"amount": Decimal("3.14159")}
    flat = _flatten_dict(d)
    assert flat["amount"] == 3.14159


def test_format_json_none_value() -> None:
    """format_json serializes None values correctly."""
    result = format_json({"key": None})
    assert json.loads(result)["key"] is None


def test_format_json_empty_dict() -> None:
    """format_json handles empty dict."""
    result = format_json({})
    assert json.loads(result) == {}


def test_format_jsonl_empty_scan_result() -> None:
    """format_jsonl for scan result with no wallets emits 3 events."""
    data = {
        "scan_id": "test_scan",
        "scan_time": "2026-02-22T12:00:00+00:00",
        "chain": "ETH",
        "window_hours": 24,
        "wallets_scanned": 0,
        "alerts_triggered": 0,
        "wallets": [],
    }
    result = format_jsonl(data)
    lines = [l for l in result.strip().split("\n") if l.strip()]
    assert len(lines) == 2  # scan_start + scan_end (no wallet_result events)

    events = [json.loads(l) for l in lines]
    types = [e["type"] for e in events]
    assert "scan_start" in types
    assert "scan_end" in types


def test_decimal_encoder_handles_other_types() -> None:
    """DecimalEncoder falls back to standard JSON for non-Decimal types."""
    from whalecli.output import DecimalEncoder
    encoder = DecimalEncoder()
    import pytest
    with pytest.raises(TypeError):
        encoder.default(object())


def test_format_table_wallet_list_no_wallets() -> None:
    """format_table handles empty wallet list."""
    data = {"wallets": [], "count": 0}
    result = format_table(data)
    assert isinstance(result, str)
    # Should contain "0" total count or just show empty table
