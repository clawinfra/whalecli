"""Output format routing (json/table/csv)."""

import json
import csv
import io
from typing import Dict, Any
from rich.console import Console
from rich.table import Table


def format_output(data: Dict[str, Any], format: str) -> str:
    """Format output data according to specified format.

    Args:
        data: Data to format.
        format: Output format (json, jsonl, table, csv).

    Returns:
        Formatted string.

    Raises:
        ValueError: If format is unknown.
    """
    formatters = {
        "json": format_json,
        "jsonl": format_jsonl,
        "table": format_table,
        "csv": format_csv
    }

    formatter = formatters.get(format)
    if not formatter:
        raise ValueError(f"Unknown format: {format}")

    return formatter(data)


def format_json(data: Dict[str, Any]) -> str:
    """Format data as structured JSON.

    Args:
        data: Data to format.

    Returns:
        JSON string.
    """
    # TODO: Implement in Builder phase
    return json.dumps(data, indent=2, default=str)


def format_jsonl(data: Dict[str, Any]) -> str:
    """Format data as JSONL (one JSON object per line).

    Args:
        data: Data to format.

    Returns:
        JSONL string.
    """
    # TODO: Implement in Builder phase
    lines = []

    # Emit scan start
    if "scan_time" in data:
        lines.append(json.dumps({
            "type": "scan_start",
            "timestamp": data.get("scan_time"),
            "chain": data.get("chain"),
            "hours": data.get("time_window_hours")
        }))

    # Emit wallet scans
    for wallet in data.get("wallets", []):
        lines.append(json.dumps({
            "type": "wallet_scan",
            "address": wallet.get("address"),
            "score": wallet.get("score"),
            "net_flow_usd": wallet.get("net_flow_usd")
        }))

    # Emit scan end
    if "wallets_scanned" in data:
        lines.append(json.dumps({
            "type": "scan_end",
            "wallets_scanned": data.get("wallets_scanned"),
            "alerts_triggered": data.get("alerts_triggered")
        }))

    return "\n".join(lines)


def format_table(data: Dict[str, Any]) -> str:
    """Format data as a Rich table for terminal display.

    Args:
        data: Data to format.

    Returns:
        Table string.
    """
    # TODO: Implement in Builder phase
    console = Console()
    table = Table(title="Whale Wallet Scan Results")

    table.add_column("Address", style="cyan")
    table.add_column("Chain", style="magenta")
    table.add_column("Label", style="green")
    table.add_column("Score", style="yellow")
    table.add_column("Net Flow (USD)", style="blue")
    table.add_column("Last Activity", style="dim")

    for wallet in data.get("wallets", []):
        table.add_row(
            wallet.get("address", "")[:10] + "...",
            wallet.get("chain", ""),
            wallet.get("label", ""),
            str(wallet.get("score", 0)),
            f"${wallet.get('net_flow_usd', 0):,.0f}",
            wallet.get("last_activity", "Never")
        )

    # Capture table output
    with io.StringIO() as buf:
        console_file = Console(file=buf)
        console_file.print(table)
        return buf.getvalue()


def format_csv(data: Dict[str, Any]) -> str:
    """Format data as CSV for spreadsheet import.

    Args:
        data: Data to format.

    Returns:
        CSV string.
    """
    # TODO: Implement in Builder phase
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    wallets = data.get("wallets", [])
    if wallets:
        writer.writerow(wallets[0].keys())

        # Write rows
        for wallet in wallets:
            writer.writerow(wallet.values())

    return output.getvalue()
