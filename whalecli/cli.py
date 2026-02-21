"""Click entry point for whalecli CLI.

This module defines all CLI commands and arguments.
"""

import click
from whalecli.config import load_config, validate_config
from whalecli.db import init_db, list_wallets, add_wallet, remove_wallet
from whalecli.output import format_output


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """whalecli — Agent-Native Whale Wallet Tracker."""
    pass


@cli.group()
def wallet():
    """Wallet management commands."""
    pass


@wallet.command("add")
@click.argument("address")
@click.option("--chain", type=click.Choice(["ETH", "BTC", "HL"]), required=True, help="Blockchain")
@click.option("--label", help="Human-readable label")
def wallet_add(address: str, chain: str, label: str | None):
    """Add a whale wallet to track."""
    # TODO: Implement in Builder phase
    click.echo(f"Adding wallet {address} on {chain}")


@wallet.command("list")
@click.option("--format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def wallet_list(format: str):
    """List all tracked whale wallets."""
    # TODO: Implement in Builder phase
    click.echo("Listing wallets")


@wallet.command("remove")
@click.argument("address")
def wallet_remove(address: str):
    """Remove a tracked whale wallet."""
    # TODO: Implement in Builder phase
    click.echo(f"Removing wallet {address}")


@wallet.command("import")
@click.argument("file_csv", type=click.Path(exists=True))
def wallet_import(file_csv: str):
    """Import whale wallets from CSV file."""
    # TODO: Implement in Builder phase
    click.echo(f"Importing wallets from {file_csv}")


@cli.command("scan")
@click.option("--chain", type=click.Choice(["ETH", "BTC", "HL"]), help="Blockchain to scan")
@click.option("--wallet", help="Specific wallet address to scan")
@click.option("--all", "scan_all", is_flag=True, help="Scan all wallets across all chains")
@click.option("--hours", type=int, default=24, help="Time window in hours")
@click.option("--threshold", type=int, help="Minimum score to include (0-100)")
@click.option("--format", type=click.Choice(["json", "jsonl", "table", "csv"]), default="json", help="Output format")
def scan_command(chain: str | None, wallet: str | None, scan_all: bool, hours: int, threshold: int | None, format: str):
    """Scan whale wallets for recent activity."""
    # TODO: Implement in Builder phase
    click.echo(f"Scanning {chain or 'all'} wallets for last {hours} hours")


@cli.group()
def alert():
    """Alert management commands."""
    pass


@alert.command("config")
@click.option("--threshold", type=float, help="Flow threshold in USD")
@click.option("--score", type=int, help="Whale score threshold (0-100)")
@click.option("--window", type=str, default="1h", help="Time window: 1h, 4h, 24h")
def alert_config(threshold: float | None, score: int | None, window: str):
    """Configure alert thresholds."""
    # TODO: Implement in Builder phase
    click.echo(f"Setting alert config: threshold={threshold}, score={score}, window={window}")


@alert.command("list")
@click.option("--format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def alert_list(format: str):
    """List active alert configuration."""
    # TODO: Implement in Builder phase
    click.echo("Listing alerts")


@cli.command("stream")
@click.option("--chain", type=click.Choice(["ETH", "BTC", "HL"]), required=True, help="Blockchain to monitor")
@click.option("--interval", type=int, default=60, help="Polling interval in seconds")
@click.option("--format", type=click.Choice(["jsonl"]), default="jsonl", help="Output format")
def stream_command(chain: str, interval: int, format: str):
    """Stream real-time whale alerts."""
    # TODO: Implement in Builder phase
    click.echo(f"Streaming {chain} alerts every {interval} seconds")


@cli.command("report")
@click.option("--wallet", help="Generate report for specific wallet")
@click.option("--summary", is_flag=True, help="Generate summary across all wallets")
@click.option("--days", type=int, default=30, help="Report period in days")
@click.option("--format", type=click.Choice(["json", "csv"]), default="json", help="Output format")
def report_command(wallet: str | None, summary: bool, days: int, format: str):
    """Generate wallet activity reports."""
    # TODO: Implement in Builder phase
    if summary:
        click.echo(f"Generating summary report for last {days} days")
    else:
        click.echo(f"Generating report for {wallet} over last {days} days")


@cli.group()
def config():
    """Configuration management commands."""
    pass


@config.command("init")
def config_init():
    """Initialize configuration file."""
    # TODO: Implement in Builder phase
    click.echo("Initializing config")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a configuration value."""
    # TODO: Implement in Builder phase
    click.echo(f"Setting {key} = {value}")


@config.command("show")
def config_show():
    """Show current configuration."""
    # TODO: Implement in Builder phase
    click.echo("Showing config")


if __name__ == "__main__":
    cli()
