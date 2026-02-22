"""Output format routing for whalecli.

Converts result dicts to the requested format: json, jsonl, table, csv.

Design rules:
- JSON: 2-space indent, deterministic key order, utf-8
- JSONL: one JSON object per line, no trailing whitespace
- Table: Rich-formatted, green=accumulating, red=distributing
- CSV: RFC 4180, header row always present

All functions return strings. The caller writes to stdout.
"""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

VALID_FORMATS = {"json", "jsonl", "table", "csv"}


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal values."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def format_output(data: Any, fmt: str) -> str:
    """
    Format data for stdout output.

    Args:
        data: Result dict, list, or any JSON-serialisable value.
        fmt: "json" | "jsonl" | "table" | "csv"

    Returns:
        Formatted string ready to write to stdout.

    Raises:
        ValueError: If fmt is not a recognised format.
    """
    fmt = fmt.lower()
    if fmt not in VALID_FORMATS:
        raise ValueError(f"Unknown format {fmt!r}. Valid: {sorted(VALID_FORMATS)}")

    if fmt == "json":
        return format_json(data)
    elif fmt == "jsonl":
        return format_jsonl(data)
    elif fmt == "table":
        return format_table(data)
    elif fmt == "csv":
        return format_csv(data)

    return format_json(data)  # fallback


# ── JSON ─────────────────────────────────────────────────────────────────────


def format_json(data: Any) -> str:
    """Pretty-print data as JSON (2-space indent)."""
    return json.dumps(data, indent=2, cls=DecimalEncoder, ensure_ascii=False)


# ── JSONL ────────────────────────────────────────────────────────────────────


def format_jsonl(data: Any) -> str:
    """
    Format as JSONL (one object per line).

    If data is a scan result dict with 'wallets' key, emits the
    documented event sequence: scan_start, wallet_result*, scan_end.

    Otherwise falls back to a single-line JSON serialisation.
    """
    lines: list[str] = []

    if isinstance(data, dict) and "wallets" in data:
        # Scan result → event sequence
        scan_id = data.get("scan_id", "")
        scan_time = data.get("scan_time", "")
        chain = data.get("chain", "all")
        window_hours = data.get("window_hours", 24)

        lines.append(
            json.dumps(
                {
                    "type": "scan_start",
                    "scan_id": scan_id,
                    "timestamp": scan_time,
                    "chain": chain,
                    "window_hours": window_hours,
                },
                cls=DecimalEncoder,
            )
        )

        for wallet in data.get("wallets", []):
            lines.append(
                json.dumps(
                    {
                        "type": "wallet_result",
                        "address": wallet.get("address", ""),
                        "chain": wallet.get("chain", ""),
                        "label": wallet.get("label", ""),
                        "score": wallet.get("score", 0),
                        "direction": wallet.get("direction", "neutral"),
                        "net_flow_usd": wallet.get("net_flow_usd", 0.0),
                        "alert_triggered": wallet.get("alert_triggered", False),
                        "timestamp": wallet.get("computed_at", scan_time),
                    },
                    cls=DecimalEncoder,
                )
            )

        lines.append(
            json.dumps(
                {
                    "type": "scan_end",
                    "scan_id": scan_id,
                    "wallets_scanned": data.get("wallets_scanned", 0),
                    "alerts_triggered": data.get("alerts_triggered", 0),
                    "timestamp": scan_time,
                },
                cls=DecimalEncoder,
            )
        )

    elif isinstance(data, list):
        for item in data:
            lines.append(json.dumps(item, cls=DecimalEncoder))

    else:
        lines.append(json.dumps(data, cls=DecimalEncoder))

    return "\n".join(lines)


# ── Table ────────────────────────────────────────────────────────────────────


def format_table(data: Any) -> str:
    """
    Format as a Rich terminal table.

    Handles:
    - Scan results (dict with 'wallets')
    - Wallet list (dict with 'wallets' and no score)
    - Alert list (dict with 'recent_alerts')
    - Alert rules (dict with 'rules')
    - Generic dict fallback
    """
    buf = io.StringIO()
    console = Console(file=buf, highlight=False, markup=True, width=120)

    if (
        isinstance(data, dict)
        and "wallets" in data
        and data["wallets"]
        and "score" in data["wallets"][0]
    ):
        _render_scan_table(console, data)
    elif isinstance(data, dict) and "wallets" in data:
        _render_wallet_list_table(console, data)
    elif isinstance(data, dict) and "recent_alerts" in data:
        _render_alerts_table(console, data)
    elif isinstance(data, dict) and "rules" in data and "recent_alerts" not in data:
        _render_rules_table(console, data)
    else:
        # Generic: dump as JSON in a panel
        console.print_json(json.dumps(data, cls=DecimalEncoder))

    return buf.getvalue()


def _direction_color(direction: str) -> str:
    if direction == "accumulating":
        return "green"
    elif direction == "distributing":
        return "red"
    return "dim"


def _score_color(score: int) -> str:
    if score >= 90:
        return "bold red"
    elif score >= 80:
        return "red"
    elif score >= 70:
        return "yellow"
    return "dim"


def _render_scan_table(console: Console, data: dict[str, Any]) -> None:
    table = Table(
        title=(
            f"Whale Scan — {data.get('chain', 'all').upper()}"
            f" | {data.get('window_hours', 24)}h window"
        ),
        show_header=True,
        header_style="bold blue",
    )
    table.add_column("Address", style="cyan", no_wrap=True)
    table.add_column("Chain", justify="center")
    table.add_column("Label", style="italic")
    table.add_column("Score", justify="right")
    table.add_column("Direction", justify="center")
    table.add_column("Net Flow USD", justify="right")
    table.add_column("Txns", justify="right")
    table.add_column("Alert", justify="center")

    for w in data.get("wallets", []):
        score = w.get("score", 0)
        direction = w.get("direction", "neutral")
        net_flow = w.get("net_flow_usd", 0.0)
        address = w.get("address", "")
        short_addr = f"{address[:8]}…{address[-6:]}" if len(address) > 16 else address

        score_text = Text(str(score), style=_score_color(score))
        dir_text = Text(direction, style=_direction_color(direction))
        flow_str = f"${net_flow:+,.0f}"
        alert_flag = "🚨" if w.get("alert_triggered") else "—"

        table.add_row(
            short_addr,
            w.get("chain", ""),
            w.get("label", ""),
            score_text,
            dir_text,
            flow_str,
            str(w.get("tx_count", 0)),
            alert_flag,
        )

    console.print(table)
    console.print(
        f"Wallets scanned: [bold]{data.get('wallets_scanned', 0)}[/bold]  "
        f"Alerts triggered: [bold red]{data.get('alerts_triggered', 0)}[/bold red]"
    )


def _render_wallet_list_table(console: Console, data: dict[str, Any]) -> None:
    table = Table(
        title="Tracked Whale Wallets",
        show_header=True,
        header_style="bold blue",
    )
    table.add_column("Address", style="cyan")
    table.add_column("Chain", justify="center")
    table.add_column("Label")
    table.add_column("Tags")
    table.add_column("Added At")

    for w in data.get("wallets", []):
        address = w.get("address", "")
        short_addr = f"{address[:10]}…{address[-6:]}" if len(address) > 18 else address
        tags_str = ", ".join(w.get("tags") or []) or "—"
        console.print()
        table.add_row(
            short_addr,
            w.get("chain", ""),
            w.get("label", "") or "—",
            tags_str,
            str(w.get("added_at", ""))[:19],
        )

    console.print(table)
    console.print(f"Total: [bold]{data.get('count', len(data.get('wallets', [])))}[/bold] wallets")


def _render_alerts_table(console: Console, data: dict[str, Any]) -> None:
    # Rules table
    if data.get("rules"):
        rules_table = Table(title="Active Rules", header_style="bold blue")
        rules_table.add_column("ID")
        rules_table.add_column("Type")
        rules_table.add_column("Value")
        rules_table.add_column("Window")
        rules_table.add_column("Chain")
        for r in data["rules"]:
            rules_table.add_row(
                r.get("id", ""),
                r.get("type", ""),
                str(r.get("value", "")),
                r.get("window", ""),
                r.get("chain") or "all",
            )
        console.print(rules_table)

    # Recent alerts table
    alerts = data.get("recent_alerts", [])
    if alerts:
        alerts_table = Table(title="Recent Alerts", header_style="bold red")
        alerts_table.add_column("ID")
        alerts_table.add_column("Address")
        alerts_table.add_column("Chain")
        alerts_table.add_column("Score", justify="right")
        alerts_table.add_column("Triggered")
        alerts_table.add_column("Webhook")
        for a in alerts:
            addr = a.get("address", "")
            short = f"{addr[:8]}…{addr[-4:]}" if len(addr) > 14 else addr
            alerts_table.add_row(
                str(a.get("id", "")),
                short,
                a.get("chain", ""),
                str(a.get("score", 0)),
                str(a.get("triggered_at", ""))[:19],
                "✅" if a.get("webhook_sent") else "—",
            )
        console.print(alerts_table)


def _render_rules_table(console: Console, data: dict[str, Any]) -> None:
    table = Table(title="Alert Rules", header_style="bold blue")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Value")
    table.add_column("Window")
    table.add_column("Chain")
    table.add_column("Active")
    for r in data.get("rules", []):
        table.add_row(
            r.get("id", ""),
            r.get("type", ""),
            str(r.get("value", "")),
            r.get("window", ""),
            r.get("chain") or "all",
            "✅" if r.get("active") else "❌",
        )
    console.print(table)


# ── CSV ──────────────────────────────────────────────────────────────────────


def format_csv(data: Any) -> str:
    """
    Format as CSV with a header row.

    Flattens nested structures to the extent possible.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)

    rows: list[dict[str, Any]] = []

    if isinstance(data, dict):
        # Try to find a list inside
        for key in ("wallets", "recent_alerts", "rules", "daily_breakdown"):
            if key in data and isinstance(data[key], list):
                rows = data[key]
                break
        if not rows and "wallet" in data and "summary" in data:
            # Single wallet report
            rows = data.get("daily_breakdown", [])

    elif isinstance(data, list):
        rows = data

    if not rows:
        writer.writerow(["value"])
        writer.writerow([json.dumps(data, cls=DecimalEncoder)])
        return buf.getvalue()

    # Flatten each row (handle nested dicts like score_breakdown)
    flat_rows = [_flatten_dict(r) for r in rows]

    if flat_rows:
        headers = list(flat_rows[0].keys())
        writer.writerow(headers)
        for row in flat_rows:
            writer.writerow([row.get(h, "") for h in headers])

    return buf.getvalue()


def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict for CSV output."""
    result: dict[str, Any] = {}
    for k, v in d.items():
        full_key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            result.update(_flatten_dict(v, full_key))
        elif isinstance(v, (list, tuple)):
            result[full_key] = json.dumps(v)
        elif isinstance(v, Decimal):
            result[full_key] = float(v)
        else:
            result[full_key] = v
    return result


# ── Utility ──────────────────────────────────────────────────────────────────


def mask_api_key(key: str) -> str:
    """
    Mask an API key for safe display.

    'abcdefg123' → 'abcd****'
    '' → '****'
    """
    if not key:
        return "****"
    if len(key) <= 4:
        return "****"
    return key[:4] + "****"
