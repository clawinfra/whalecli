"""
Custom exception hierarchy for whalecli.

Each exception maps to a specific CLI exit code and JSON error_code field.
cli.py catches all WhalecliError subclasses and formats them as JSON output.

Exit code mapping:
  1 — WhalecliError (generic CLI error)
  2 — APIError (invalid key, rate limit, upstream error)
  3 — NetworkError (timeout, connection refused)
  4 — DataError (invalid address, wallet not found)
  5 — ConfigError (missing/malformed config)
  6 — DatabaseError (SQLite failure)
"""


class WhalecliError(Exception):
    """Base exception for all whalecli errors."""

    exit_code: int = 1
    error_code: str = "unknown_error"

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class APIError(WhalecliError):
    """Upstream API returned an error response."""

    exit_code = 2
    error_code = "api_error"


class InvalidAPIKeyError(APIError):
    """API key is invalid or missing."""

    error_code = "invalid_api_key"


class RateLimitError(APIError):
    """API rate limit exceeded."""

    error_code = "rate_limited"

    def __init__(self, message: str, retry_after: int = 60, **kwargs) -> None:
        super().__init__(message, details={"retry_after_seconds": retry_after})
        self.retry_after = retry_after


class NetworkError(WhalecliError):
    """Network connectivity issue — timeout or connection failure."""

    exit_code = 3
    error_code = "network_error"


class NetworkTimeoutError(NetworkError):
    """Request timed out."""

    error_code = "network_timeout"


class ConnectionFailedError(NetworkError):
    """Could not connect to API endpoint."""

    error_code = "connection_failed"


class DataError(WhalecliError):
    """Data validation or not-found error."""

    exit_code = 4
    error_code = "data_error"


class InvalidAddressError(DataError):
    """Address format is invalid for the given chain."""

    error_code = "invalid_address"


class WalletNotFoundError(DataError):
    """Wallet address is not in the tracked wallet list."""

    error_code = "wallet_not_found"


class WalletExistsError(DataError):
    """Wallet is already in the tracked list (on wallet add)."""

    error_code = "wallet_exists"


class NoTransactionsError(DataError):
    """No transactions found in the specified window."""

    error_code = "no_transactions"


class ConfigError(WhalecliError):
    """Config file is missing or malformed."""

    exit_code = 5
    error_code = "config_error"


class ConfigMissingError(ConfigError):
    """Config file does not exist; user should run `whalecli config init`."""

    error_code = "config_missing"


class ConfigInvalidError(ConfigError):
    """Config file exists but contains invalid TOML or invalid values."""

    error_code = "config_invalid"


class DatabaseError(WhalecliError):
    """SQLite operation failed."""

    exit_code = 6
    error_code = "db_error"
