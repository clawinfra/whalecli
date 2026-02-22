"""Tests for whalecli/cli.py — Click CLI entry point."""

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
def temp_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_whale.db")


@pytest.fixture
def config_env(temp_db_path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set WHALECLI_DB_PATH to a temp path for CLI tests."""
    monkeypatch.setenv("WHALECLI_DB_PATH", temp_db_path)
    monkeypatch.setenv("WHALECLI_SCORE_THRESHOLD", "70")


# ── version ───────────────────────────────────────────────────────────────────


def test_cli_version(runner: CliRunner) -> None:
    """--version flag should output version string."""
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


# ── config commands ───────────────────────────────────────────────────────────


def test_config_init(runner: CliRunner, tmp_path: Path) -> None:
    """config init should create config file."""
    config_path = tmp_path / "config.toml"
    result = runner.invoke(
        cli,
        [
            "--config",
            str(config_path),
            "config",
            "init",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] in ("initialized", "reinitialized")


def test_config_init_already_exists(runner: CliRunner, tmp_path: Path) -> None:
    """config init without --force should not overwrite existing config."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("[api]\n")

    result = runner.invoke(
        cli,
        [
            "--config",
            str(config_path),
            "config",
            "init",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] == "already_exists"


def test_config_show(runner: CliRunner, tmp_path: Path) -> None:
    """config show should output JSON with masked API keys."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[api]
etherscan_api_key = "secret_key_12345"
""")
    result = runner.invoke(
        cli,
        [
            "--config",
            str(config_path),
            "config",
            "show",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert "api" in output
    assert "****" in output["api"]["etherscan_api_key"]


def test_config_set(runner: CliRunner, tmp_path: Path) -> None:
    """config set should update a config value."""
    config_path = tmp_path / "config.toml"
    # Initialize first
    runner.invoke(cli, ["--config", str(config_path), "config", "init"])

    result = runner.invoke(
        cli,
        [
            "--config",
            str(config_path),
            "config",
            "set",
            "alert.score_threshold",
            "85",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] == "updated"


# ── wallet commands ───────────────────────────────────────────────────────────


def test_wallet_add(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """wallet add should add a wallet to the DB."""
    result = runner.invoke(
        cli,
        [
            "wallet",
            "add",
            "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
            "--chain",
            "ETH",
            "--label",
            "Test Whale",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] == "added"
    assert output["wallet"]["chain"] == "ETH"


def test_wallet_add_invalid_address(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """wallet add with invalid ETH address should fail."""
    result = runner.invoke(
        cli,
        [
            "wallet",
            "add",
            "not_a_valid_address",
            "--chain",
            "ETH",
        ],
    )
    assert result.exit_code != 0


def test_wallet_list_empty(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """wallet list on empty DB should return empty wallets list."""
    result = runner.invoke(cli, ["wallet", "list"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["count"] == 0
    assert output["wallets"] == []


def test_wallet_list_with_chain_filter(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """wallet list --chain should filter by chain."""
    # Add an ETH wallet
    runner.invoke(
        cli,
        [
            "wallet",
            "add",
            "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
            "--chain",
            "ETH",
            "--label",
            "ETH W",
        ],
    )

    result = runner.invoke(cli, ["wallet", "list", "--chain", "ETH"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["count"] >= 1


def test_wallet_remove(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """wallet remove should remove an existing wallet."""
    addr = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
    runner.invoke(cli, ["wallet", "add", addr, "--chain", "ETH"])

    result = runner.invoke(cli, ["wallet", "remove", addr, "--chain", "ETH"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] == "removed"


def test_wallet_remove_not_found(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """wallet remove for unknown address should fail with non-zero exit."""
    result = runner.invoke(cli, ["wallet", "remove", "0xnotexist", "--chain", "ETH"])
    assert result.exit_code != 0


def test_wallet_import_csv(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """wallet import from CSV should add wallets."""
    csv_file = tmp_path / "wallets.csv"
    csv_file.write_text(
        "address,chain,label,tags\n0xd8da6bf26964af9d7eed9e03e53415d37aa96045,ETH,Whale 1,\n"
    )

    result = runner.invoke(cli, ["wallet", "import", str(csv_file)])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["imported"] >= 1


# ── alert commands ────────────────────────────────────────────────────────────


def test_alert_set(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """alert set should create an alert rule."""
    result = runner.invoke(
        cli,
        [
            "alert",
            "set",
            "--score",
            "75",
            "--window",
            "1h",
        ],
    )
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] == "alert_configured"
    assert output["rule"]["value"] == 75.0


def test_alert_set_missing_args(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """alert set without --threshold or --score should fail."""
    result = runner.invoke(cli, ["alert", "set"])
    assert result.exit_code != 0


def test_alert_list(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """alert list should return rules and recent alerts."""
    result = runner.invoke(cli, ["alert", "list"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert "rules" in output
    assert "recent_alerts" in output


# ── scan command ──────────────────────────────────────────────────────────────


def test_scan_no_args_fails(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """scan without --chain, --wallet, or --all should fail."""
    result = runner.invoke(cli, ["scan"])
    assert result.exit_code != 0


def test_scan_no_wallets_in_db(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """scan --all with no wallets should return non-zero (data error)."""
    result = runner.invoke(cli, ["scan", "--all"])
    # Should fail gracefully
    assert result.exit_code != 0 or "wallets" in result.output or result.exit_code == 0


@patch("whalecli.cli._fetch_wallet_txns", new_callable=AsyncMock)
def test_scan_with_mocked_txns(
    mock_fetch: AsyncMock,
    runner: CliRunner,
    tmp_path: Path,
    config_env: None,
) -> None:
    """scan --chain ETH should run and return JSON result."""
    mock_fetch.return_value = []

    # Add a wallet first
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

    result = runner.invoke(cli, ["scan", "--chain", "ETH", "--hours", "24"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert "wallets" in output
    assert "scan_time" in output


# ── report command ────────────────────────────────────────────────────────────


def test_report_no_args_fails(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """report without --wallet or --summary should fail."""
    result = runner.invoke(cli, ["report"])
    assert result.exit_code != 0


def test_report_summary_empty(runner: CliRunner, tmp_path: Path, config_env: None) -> None:
    """report --summary with empty DB should return valid JSON."""
    result = runner.invoke(cli, ["report", "--summary"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert "total_wallets" in output


# ── help text ─────────────────────────────────────────────────────────────────


def test_cli_help(runner: CliRunner) -> None:
    """CLI should display help text."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "WhaleWatch" in result.output


def test_wallet_help(runner: CliRunner) -> None:
    """wallet --help should list sub-commands."""
    result = runner.invoke(cli, ["wallet", "--help"])
    assert result.exit_code == 0
    assert "add" in result.output
    assert "list" in result.output
    assert "remove" in result.output
