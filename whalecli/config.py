"""Configuration management for whalecli.

Loads config from ~/.whalecli/config.toml with environment variable overrides.
"""

import os
import tomllib
from pathlib import Path
from dataclasses import dataclass
from typing import Literal


@dataclass
class ApiConfig:
    """API configuration."""
    etherscan_api_key: str
    blockchain_info_api_key: str = ""


@dataclass
class AlertConfig:
    """Alert configuration."""
    score_threshold: int = 70
    flow_threshold_usd: float = 1_000_000
    window_minutes: int = 60
    webhook_url: str = ""


@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: str = "~/.whalecli/whale.db"
    cache_ttl_hours: int = 24


@dataclass
class OutputConfig:
    """Output configuration."""
    default_format: Literal["json", "jsonl", "table", "csv"] = "json"
    timezone: str = "UTC"


@dataclass
class Config:
    """Complete configuration."""
    api: ApiConfig
    alert: AlertConfig
    database: DatabaseConfig
    output: OutputConfig


DEFAULT_CONFIG_PATH = Path.home() / ".whalecli" / "config.toml"


def load_config(path: str | None = None) -> Config:
    """Load configuration from TOML file.

    Args:
        path: Path to config file. If None, uses DEFAULT_CONFIG_PATH.

    Returns:
        Config object.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config is invalid.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Return default config
    return Config(
        api=ApiConfig(
            etherscan_api_key=os.getenv("WHALECLI_ETHERSCAN_API_KEY", ""),
            blockchain_info_api_key=os.getenv("WHALECLI_BLOCKCHAIN_INFO_API_KEY", "")
        ),
        alert=AlertConfig(),
        database=DatabaseConfig(),
        output=OutputConfig()
    )


def validate_config(config: Config) -> bool:
    """Validate configuration.

    Args:
        config: Config object to validate.

    Returns:
        True if valid, False otherwise.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Basic validation
    if not config.api.etherscan_api_key:
        return False
    return True


def get_api_key(provider: str) -> str:
    """Get API key for a provider.

    Args:
        provider: Provider name (e.g., "etherscan").

    Returns:
        API key string.

    Raises:
        ValueError: If provider is unknown or key not found.
    """
    # TODO: Implement in Builder phase
    config = load_config()
    if provider == "etherscan":
        return config.api.etherscan_api_key
    raise ValueError(f"Unknown provider: {provider}")


def init_config() -> Path:
    """Initialize default configuration file.

    Returns:
        Path to created config file.

    Raises:
        FileExistsError: If config file already exists.
    """
    # TODO: Implement in Builder phase
    config_path = Path.home() / ".whalecli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    default_config = """
[api]
etherscan_api_key = ""
blockchain_info_api_key = ""

[alert]
score_threshold = 70
flow_threshold_usd = 1000000
window_minutes = 60
webhook_url = ""

[database]
path = "~/.whalecli/whale.db"
cache_ttl_hours = 24

[output]
default_format = "json"
timezone = "UTC"
""".strip()

    config_path.write_text(default_config)
    return config_path
