"""Additional coverage tests for cli.py — uncovered paths."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from whalecli.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def config_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("WHALECLI_DB_PATH", db_path)
    monkeypatch.setenv("WHALECLI_SCORE_THRESHOLD", "70")
    return db_path


def test_wallet_list_table_format(runner: CliRunner, config_env: str) -> None:
    """wallet list --format table should return table output."""
    result = runner.invoke(cli, ["wallet", "list", "--format", "table"])
    assert result.exit_code == 0
    # Table output doesn't have to be JSON


def test_wallet_list_csv_format(runner: CliRunner, config_env: str) -> None:
    """wallet list --format csv should return CSV output."""
    result = runner.invoke(cli, ["wallet", "list", "--format", "csv"])
    assert result.exit_code == 0


def test_alert_set_flow_threshold(runner: CliRunner, config_env: str) -> None:
    """alert set --threshold should create a flow-type rule."""
    result = runner.invoke(
        cli,
        [
            "alert",
            "set",
            "--threshold",
            "5000000",
            "--window",
            "4h",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["rule"]["type"] == "flow"
    assert output["rule"]["value"] == 5_000_000.0


def test_alert_set_with_chain(runner: CliRunner, config_env: str) -> None:
    """alert set with --chain filter."""
    result = runner.invoke(
        cli,
        [
            "alert",
            "set",
            "--score",
            "80",
            "--chain",
            "BTC",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["rule"]["chain"] == "BTC"


def test_alert_list_table_format(runner: CliRunner, config_env: str) -> None:
    """alert list --format table should work."""
    result = runner.invoke(cli, ["alert", "list", "--format", "table"])
    assert result.exit_code == 0


def test_config_show_json(runner: CliRunner, config_env: str) -> None:
    """config show should return JSON output."""
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert "api" in output
    assert "alert" in output


def test_config_init_force_overwrites(runner: CliRunner, tmp_path: Path) -> None:
    """config init --force should reinitialize an existing config."""
    config_path = tmp_path / "config.toml"
    # First init
    runner.invoke(cli, ["--config", str(config_path), "config", "init"])
    # Force reinit
    result = runner.invoke(cli, ["--config", str(config_path), "config", "init", "--force"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] == "reinitialized"
    assert "backup" in output


def test_wallet_add_btc(runner: CliRunner, config_env: str) -> None:
    """wallet add should work for BTC addresses."""
    result = runner.invoke(
        cli,
        [
            "wallet",
            "add",
            "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
            "--chain",
            "BTC",
            "--label",
            "BTC Whale",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["wallet"]["chain"] == "BTC"


def test_wallet_add_with_tags(runner: CliRunner, config_env: str) -> None:
    """wallet add with tags should save them."""
    result = runner.invoke(
        cli,
        [
            "wallet",
            "add",
            "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
            "--chain",
            "ETH",
            "--tag",
            "exchange",
            "--tag",
            "binance",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert "exchange" in output["wallet"]["tags"]


def test_wallet_add_duplicate(runner: CliRunner, config_env: str) -> None:
    """wallet add duplicate address should fail with non-zero exit."""
    addr = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
    runner.invoke(cli, ["wallet", "add", addr, "--chain", "ETH"])
    result = runner.invoke(cli, ["wallet", "add", addr, "--chain", "ETH"])
    assert result.exit_code != 0


def test_report_wallet_not_tracked(runner: CliRunner, config_env: str) -> None:
    """report for untracked wallet should fail."""
    result = runner.invoke(
        cli,
        [
            "report",
            "--wallet",
            "0xnottracked",
            "--chain",
            "ETH",
        ],
    )
    assert result.exit_code != 0


def test_report_summary_with_wallets(runner: CliRunner, config_env: str) -> None:
    """report --summary with wallets in DB returns full report."""
    # Add a wallet
    runner.invoke(
        cli,
        [
            "wallet",
            "add",
            "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
            "--chain",
            "ETH",
        ],
    )

    result = runner.invoke(cli, ["report", "--summary", "--days", "7"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert "total_wallets" in output
    assert output["total_wallets"] >= 1


@patch("whalecli.cli._fetch_wallet_txns", new_callable=AsyncMock)
def test_scan_format_table(
    mock_fetch: AsyncMock,
    runner: CliRunner,
    config_env: str,
) -> None:
    """scan --format table should not error."""
    mock_fetch.return_value = []

    # Add a wallet
    runner.invoke(
        cli,
        [
            "wallet",
            "add",
            "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
            "--chain",
            "ETH",
        ],
    )

    result = runner.invoke(cli, ["scan", "--chain", "ETH", "--format", "table"])
    assert result.exit_code == 0


@patch("whalecli.cli._fetch_wallet_txns", new_callable=AsyncMock)
def test_scan_format_jsonl(
    mock_fetch: AsyncMock,
    runner: CliRunner,
    config_env: str,
) -> None:
    """scan --format jsonl emits JSONL events."""
    mock_fetch.return_value = []

    runner.invoke(
        cli,
        [
            "wallet",
            "add",
            "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
            "--chain",
            "ETH",
        ],
    )

    result = runner.invoke(cli, ["scan", "--chain", "ETH", "--format", "jsonl"])
    assert result.exit_code == 0
    for line in result.output.strip().split("\n"):
        if line.strip():
            json.loads(line)  # each line is valid JSON


@patch("whalecli.cli._fetch_wallet_txns", new_callable=AsyncMock)
def test_scan_all_flag(
    mock_fetch: AsyncMock,
    runner: CliRunner,
    config_env: str,
) -> None:
    """scan --all scans all tracked wallets."""
    mock_fetch.return_value = []

    runner.invoke(
        cli,
        [
            "wallet",
            "add",
            "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
            "--chain",
            "ETH",
        ],
    )

    result = runner.invoke(cli, ["scan", "--all"])
    assert result.exit_code == 0


def test_wallet_remove_purge(runner: CliRunner, config_env: str) -> None:
    """wallet remove --purge should delete tx history too."""
    addr = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
    runner.invoke(cli, ["wallet", "add", addr, "--chain", "ETH"])

    result = runner.invoke(cli, ["wallet", "remove", addr, "--chain", "ETH", "--purge"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] == "removed"


def test_global_format_override(runner: CliRunner, config_env: str) -> None:
    """--format flag at root level should override default output format."""
    result = runner.invoke(
        cli,
        [
            "--format",
            "json",
            "wallet",
            "list",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert "wallets" in output


@patch("whalecli.cli._fetch_wallet_txns", new_callable=AsyncMock)
def test_report_single_wallet(
    mock_fetch: AsyncMock,
    runner: CliRunner,
    config_env: str,
) -> None:
    """report --wallet should return single wallet report."""
    addr = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
    # Add wallet and a score first
    runner.invoke(cli, ["wallet", "add", addr, "--chain", "ETH", "--label", "My Whale"])

    # The report uses score history from DB which is empty, but should still work
    result = runner.invoke(cli, ["report", "--wallet", addr, "--chain", "ETH"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert "wallet" in output
    assert "summary" in output
    assert "daily_breakdown" in output


def test_config_set_invalid_section(runner: CliRunner, config_env: str, tmp_path) -> None:
    """config set with invalid section should fail."""
    config_path = tmp_path / "cfg.toml"
    runner.invoke(cli, ["--config", str(config_path), "config", "init"])
    result = runner.invoke(
        cli,
        [
            "--config",
            str(config_path),
            "config",
            "set",
            "nonexistent.key",
            "value",
        ],
    )
    assert result.exit_code != 0


def test_config_set_invalid_key(runner: CliRunner, config_env: str, tmp_path) -> None:
    """config set with invalid key within valid section should fail."""
    config_path = tmp_path / "cfg.toml"
    runner.invoke(cli, ["--config", str(config_path), "config", "init"])
    result = runner.invoke(
        cli,
        [
            "--config",
            str(config_path),
            "config",
            "set",
            "alert.nonexistent_field",
            "value",
        ],
    )
    assert result.exit_code != 0


def test_config_set_bool_value(runner: CliRunner, tmp_path) -> None:
    """config set should handle boolean values."""
    config_path = tmp_path / "config.toml"
    runner.invoke(cli, ["--config", str(config_path), "config", "init"])
    result = runner.invoke(
        cli,
        [
            "--config",
            str(config_path),
            "config",
            "set",
            "output.color",
            "false",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] == "updated"


def test_wallet_import_csv_dry_run(runner: CliRunner, config_env: str, tmp_path) -> None:
    """wallet import --dry-run should not persist wallets."""
    csv_file = tmp_path / "wallets.csv"
    csv_file.write_text(
        "address,chain,label,tags\n" "0xd8da6bf26964af9d7eed9e03e53415d37aa96045,ETH,Whale A,\n"
    )
    result = runner.invoke(cli, ["wallet", "import", str(csv_file), "--dry-run"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert "would_import" in output

    # Verify not actually added
    list_result = runner.invoke(cli, ["wallet", "list"])
    list_output = json.loads(list_result.output)
    assert list_output["count"] == 0
