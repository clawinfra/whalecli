"""Tests for whalecli/config.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from whalecli.config import (
    WhalecliConfig,
    get_default_config_path,
    load_config,
    save_config,
)
from whalecli.exceptions import ConfigInvalidError

# ── load_config ───────────────────────────────────────────────────────────────


def test_load_config_returns_defaults_when_no_file(tmp_path: Path) -> None:
    """load_config should return defaults when config file doesn't exist."""
    missing = tmp_path / "nonexistent.toml"
    config = load_config(str(missing))
    assert isinstance(config, WhalecliConfig)
    assert config.alert.score_threshold == 70
    assert config.output.default_format == "json"


def test_load_config_from_valid_toml(tmp_path: Path) -> None:
    """load_config should correctly parse a valid TOML config."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[api]
etherscan_api_key = "my_key_123"

[alert]
score_threshold = 80
flow_threshold_usd = 5000000.0

[database]
path = "/tmp/test_whale.db"

[output]
default_format = "table"
""")
    config = load_config(str(config_file))
    assert config.api.etherscan_api_key == "my_key_123"
    assert config.alert.score_threshold == 80
    assert config.alert.flow_threshold_usd == 5_000_000.0
    assert config.output.default_format == "table"


def test_load_config_invalid_toml(tmp_path: Path) -> None:
    """load_config should raise ConfigInvalidError on bad TOML syntax."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("this is not valid toml = [broken")
    with pytest.raises(ConfigInvalidError):
        load_config(str(config_file))


def test_load_config_invalid_score_threshold(tmp_path: Path) -> None:
    """load_config should raise ConfigInvalidError for score_threshold > 100."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[alert]
score_threshold = 150
""")
    with pytest.raises(ConfigInvalidError):
        load_config(str(config_file))


def test_load_config_invalid_format(tmp_path: Path) -> None:
    """load_config should raise ConfigInvalidError for unknown output format."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[output]
default_format = "xml"
""")
    with pytest.raises(ConfigInvalidError):
        load_config(str(config_file))


def test_load_config_negative_flow_threshold(tmp_path: Path) -> None:
    """load_config should raise ConfigInvalidError for negative flow threshold."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[alert]
flow_threshold_usd = -1000
""")
    with pytest.raises(ConfigInvalidError):
        load_config(str(config_file))


# ── Environment variable overrides ───────────────────────────────────────────


def test_env_override_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """WHALECLI_ETHERSCAN_API_KEY env var overrides config file value."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('[api]\netherscan_api_key = "file_key"')

    monkeypatch.setenv("WHALECLI_ETHERSCAN_API_KEY", "env_key_xyz")
    config = load_config(str(config_file))
    assert config.api.etherscan_api_key == "env_key_xyz"


def test_env_override_score_threshold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """WHALECLI_SCORE_THRESHOLD env var overrides config file value."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("")  # empty file

    monkeypatch.setenv("WHALECLI_SCORE_THRESHOLD", "85")
    config = load_config(str(config_file))
    assert config.alert.score_threshold == 85


def test_env_override_invalid_type(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Invalid env var type should raise ConfigInvalidError."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("")

    monkeypatch.setenv("WHALECLI_SCORE_THRESHOLD", "not_a_number")
    with pytest.raises(ConfigInvalidError):
        load_config(str(config_file))


def test_env_override_webhook_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """WHALECLI_WEBHOOK_URL env var sets webhook URL."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("")

    monkeypatch.setenv("WHALECLI_WEBHOOK_URL", "https://hooks.example.com/test")
    config = load_config(str(config_file))
    assert config.alert.webhook_url == "https://hooks.example.com/test"


def test_env_no_color(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """WHALECLI_NO_COLOR env var disables color."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("")

    monkeypatch.setenv("WHALECLI_NO_COLOR", "1")
    config = load_config(str(config_file))
    assert config.output.color is False


def test_env_cloud_enabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """WHALECLI_CLOUD_ENABLED sets cloud mode."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("")

    monkeypatch.setenv("WHALECLI_CLOUD_ENABLED", "true")
    config = load_config(str(config_file))
    assert config.cloud.enabled is True


# ── save_config ───────────────────────────────────────────────────────────────


def test_save_config_roundtrip(tmp_path: Path) -> None:
    """save_config → load_config should round-trip without data loss."""
    config = WhalecliConfig()
    config.api.etherscan_api_key = "saved_key"
    config.alert.score_threshold = 75

    config_path = tmp_path / "config.toml"
    save_config(config, str(config_path))

    loaded = load_config(str(config_path))
    assert loaded.api.etherscan_api_key == "saved_key"
    assert loaded.alert.score_threshold == 75


def test_save_config_creates_dir(tmp_path: Path) -> None:
    """save_config should create parent directory if it doesn't exist."""
    nested = tmp_path / "a" / "b" / "c" / "config.toml"
    config = WhalecliConfig()
    save_config(config, str(nested))
    assert nested.exists()


# ── get_default_config_path ───────────────────────────────────────────────────


def test_get_default_config_path() -> None:
    """Default config path should be in user home directory."""
    path = get_default_config_path()
    assert ".whalecli" in str(path)
    assert path.name == "config.toml"
