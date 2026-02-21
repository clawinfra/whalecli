"""
Config loading for whalecli.

Sources (in precedence order, highest first):
  1. Environment variables (WHALECLI_*)
  2. ~/.whalecli/config.toml
  3. Built-in defaults

Usage:
    from whalecli.config import load_config
    config = load_config()
    print(config.api.etherscan_api_key)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import toml

from whalecli.exceptions import ConfigInvalidError, ConfigMissingError

# Default config directory and file
DEFAULT_CONFIG_DIR = Path.home() / ".whalecli"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"

# Environment variable → config key mapping
# Format: (env_var_name, dotted_config_path, type_converter)
_ENV_OVERRIDES: list[tuple[str, str, type]] = [
    ("WHALECLI_ETHERSCAN_API_KEY", "api.etherscan_api_key", str),
    ("WHALECLI_BLOCKCHAIN_INFO_KEY", "api.blockchain_info_api_key", str),
    ("WHALECLI_HYPERLIQUID_KEY", "api.hyperliquid_api_key", str),
    ("WHALECLI_SCORE_THRESHOLD", "alert.score_threshold", int),
    ("WHALECLI_FLOW_THRESHOLD_USD", "alert.flow_threshold_usd", float),
    ("WHALECLI_WEBHOOK_URL", "alert.webhook_url", str),
    ("WHALECLI_DB_PATH", "database.path", str),
    ("WHALECLI_CACHE_TTL_HOURS", "database.cache_ttl_hours", int),
    ("WHALECLI_OUTPUT_FORMAT", "output.default_format", str),
    ("WHALECLI_TIMEZONE", "output.timezone", str),
    ("WHALECLI_CLOUD_URL", "cloud.url", str),
    ("WHALECLI_CLOUD_TOKEN", "cloud.api_token", str),
]

VALID_FORMATS = {"json", "jsonl", "table", "csv"}
VALID_CHAINS = {"ETH", "BTC", "HL"}


@dataclass
class APIConfig:
    """API key configuration."""

    etherscan_api_key: str = ""
    blockchain_info_api_key: str = ""
    hyperliquid_api_key: str = ""


@dataclass
class AlertConfig:
    """Alert threshold and delivery configuration."""

    score_threshold: int = 70           # 0–100; scores >= this trigger alerts
    flow_threshold_usd: float = 1_000_000.0
    window_minutes: int = 60
    webhook_url: str = ""
    webhook_secret: str = ""


@dataclass
class DatabaseConfig:
    """SQLite database and caching configuration."""

    path: str = str(DEFAULT_CONFIG_DIR / "whale.db")
    cache_ttl_hours: int = 24


@dataclass
class OutputConfig:
    """Output formatting defaults."""

    default_format: str = "json"        # json | jsonl | table | csv
    timezone: str = "UTC"
    color: bool = True


@dataclass
class CloudConfig:
    """Cloud backend configuration (Phase 2)."""

    enabled: bool = False
    url: str = ""
    api_token: str = ""


@dataclass
class WhalecliConfig:
    """Full configuration object. Passed via Click context to all commands."""

    api: APIConfig = field(default_factory=APIConfig)
    alert: AlertConfig = field(default_factory=AlertConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)


def load_config(path: str | None = None) -> WhalecliConfig:
    """
    Load configuration from TOML file + environment variable overrides.

    Args:
        path: Override config file path. If None, uses WHALECLI_CONFIG_PATH
              env var or default (~/.whalecli/config.toml).

    Returns:
        WhalecliConfig with all values resolved.

    Raises:
        ConfigMissingError: Config file not found and no defaults possible.
        ConfigInvalidError: Config file exists but is invalid TOML or values.
    """
    config_path = _resolve_config_path(path)

    raw: dict = {}
    if config_path.exists():
        try:
            raw = toml.load(str(config_path))
        except toml.TomlDecodeError as e:
            raise ConfigInvalidError(f"Invalid TOML in {config_path}: {e}") from e

    config = _dict_to_config(raw)
    _apply_env_overrides(config)
    _validate_config(config)

    return config


def save_config(config: WhalecliConfig, path: str | None = None) -> Path:
    """
    Serialize WhalecliConfig to TOML and write to disk.

    Returns the path where config was written.
    """
    config_path = _resolve_config_path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "api": {
            "etherscan_api_key": config.api.etherscan_api_key,
            "blockchain_info_api_key": config.api.blockchain_info_api_key,
            "hyperliquid_api_key": config.api.hyperliquid_api_key,
        },
        "alert": {
            "score_threshold": config.alert.score_threshold,
            "flow_threshold_usd": config.alert.flow_threshold_usd,
            "window_minutes": config.alert.window_minutes,
            "webhook_url": config.alert.webhook_url,
            "webhook_secret": config.alert.webhook_secret,
        },
        "database": {
            "path": config.database.path,
            "cache_ttl_hours": config.database.cache_ttl_hours,
        },
        "output": {
            "default_format": config.output.default_format,
            "timezone": config.output.timezone,
            "color": config.output.color,
        },
        "cloud": {
            "enabled": config.cloud.enabled,
            "url": config.cloud.url,
            "api_token": config.cloud.api_token,
        },
    }

    with open(config_path, "w") as f:
        toml.dump(data, f)

    return config_path


def get_default_config_path() -> Path:
    """Return the default config file path."""
    return DEFAULT_CONFIG_PATH


# ──────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────


def _resolve_config_path(path: str | None) -> Path:
    if path:
        return Path(path).expanduser()
    env_path = os.environ.get("WHALECLI_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return DEFAULT_CONFIG_PATH


def _dict_to_config(raw: dict) -> WhalecliConfig:
    """Build WhalecliConfig from raw TOML dict, applying defaults for missing keys."""
    config = WhalecliConfig()

    api = raw.get("api", {})
    config.api.etherscan_api_key = api.get("etherscan_api_key", "")
    config.api.blockchain_info_api_key = api.get("blockchain_info_api_key", "")
    config.api.hyperliquid_api_key = api.get("hyperliquid_api_key", "")

    alert = raw.get("alert", {})
    config.alert.score_threshold = int(alert.get("score_threshold", 70))
    config.alert.flow_threshold_usd = float(alert.get("flow_threshold_usd", 1_000_000.0))
    config.alert.window_minutes = int(alert.get("window_minutes", 60))
    config.alert.webhook_url = alert.get("webhook_url", "")
    config.alert.webhook_secret = alert.get("webhook_secret", "")

    db = raw.get("database", {})
    config.database.path = db.get("path", str(DEFAULT_CONFIG_DIR / "whale.db"))
    config.database.cache_ttl_hours = int(db.get("cache_ttl_hours", 24))

    output = raw.get("output", {})
    config.output.default_format = output.get("default_format", "json")
    config.output.timezone = output.get("timezone", "UTC")
    config.output.color = bool(output.get("color", True))

    cloud = raw.get("cloud", {})
    config.cloud.enabled = bool(cloud.get("enabled", False))
    config.cloud.url = cloud.get("url", "")
    config.cloud.api_token = cloud.get("api_token", "")

    return config


def _apply_env_overrides(config: WhalecliConfig) -> None:
    """Apply environment variable overrides to a loaded config."""
    # Handle WHALECLI_CLOUD_ENABLED separately (bool from string)
    cloud_enabled = os.environ.get("WHALECLI_CLOUD_ENABLED")
    if cloud_enabled is not None:
        config.cloud.enabled = cloud_enabled.lower() in ("1", "true", "yes")

    # Handle WHALECLI_NO_COLOR
    if os.environ.get("WHALECLI_NO_COLOR"):
        config.output.color = False

    for env_var, dotted_key, converter in _ENV_OVERRIDES:
        val = os.environ.get(env_var)
        if val is None:
            continue
        section, key = dotted_key.split(".", 1)
        section_obj = getattr(config, section)
        try:
            setattr(section_obj, key, converter(val))
        except (ValueError, TypeError) as e:
            raise ConfigInvalidError(
                f"Invalid value for {env_var}={val!r}: {e}"
            ) from e


def _validate_config(config: WhalecliConfig) -> None:
    """Validate config values. Raises ConfigInvalidError on invalid values."""
    if not 0 <= config.alert.score_threshold <= 100:
        raise ConfigInvalidError(
            f"alert.score_threshold must be 0–100, got {config.alert.score_threshold}"
        )
    if config.output.default_format not in VALID_FORMATS:
        raise ConfigInvalidError(
            f"output.default_format must be one of {VALID_FORMATS}, "
            f"got {config.output.default_format!r}"
        )
    if config.alert.flow_threshold_usd < 0:
        raise ConfigInvalidError(
            f"alert.flow_threshold_usd must be non-negative, "
            f"got {config.alert.flow_threshold_usd}"
        )


# ── Backward-compatibility aliases ────────────────────────────────────────────
# Old name → new name
ApiConfig = APIConfig
Config = WhalecliConfig
