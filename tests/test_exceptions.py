"""Tests for whalecli/exceptions.py — exception hierarchy."""

from __future__ import annotations

from whalecli.exceptions import (
    APIError,
    ConfigError,
    ConfigInvalidError,
    ConfigMissingError,
    ConnectionFailedError,
    DatabaseError,
    DataError,
    InvalidAddressError,
    InvalidAPIKeyError,
    NetworkError,
    NetworkTimeoutError,
    NoTransactionsError,
    RateLimitError,
    WalletExistsError,
    WalletNotFoundError,
    WhalecliError,
)

# ── Hierarchy / exit codes ────────────────────────────────────────────────────


def test_whalecli_error_base() -> None:
    """WhalecliError is the base of the hierarchy."""
    e = WhalecliError("base error")
    assert e.exit_code == 1
    assert e.error_code == "unknown_error"
    assert str(e) == "base error"


def test_api_error_exit_code() -> None:
    """APIError has exit_code 2."""
    e = APIError("api broken")
    assert e.exit_code == 2
    assert isinstance(e, WhalecliError)


def test_invalid_api_key_inherits_api_error() -> None:
    """InvalidAPIKeyError is a subtype of APIError."""
    e = InvalidAPIKeyError("key invalid")
    assert isinstance(e, APIError)
    assert e.error_code == "invalid_api_key"


def test_rate_limit_error() -> None:
    """RateLimitError includes retry_after."""
    e = RateLimitError("too many requests", retry_after=30)
    assert e.retry_after == 30
    assert e.details["retry_after_seconds"] == 30


def test_network_error_exit_code() -> None:
    """NetworkError has exit_code 3."""
    e = NetworkError("connection refused")
    assert e.exit_code == 3


def test_network_timeout_inherits() -> None:
    """NetworkTimeoutError inherits from NetworkError."""
    e = NetworkTimeoutError("timed out")
    assert isinstance(e, NetworkError)


def test_connection_failed_inherits() -> None:
    """ConnectionFailedError inherits from NetworkError."""
    e = ConnectionFailedError("can't connect")
    assert isinstance(e, NetworkError)


def test_data_error_exit_code() -> None:
    """DataError has exit_code 4."""
    e = DataError("not found")
    assert e.exit_code == 4


def test_invalid_address_inherits() -> None:
    """InvalidAddressError inherits from DataError."""
    e = InvalidAddressError("bad address")
    assert isinstance(e, DataError)


def test_wallet_not_found_inherits() -> None:
    """WalletNotFoundError inherits from DataError."""
    e = WalletNotFoundError("wallet missing")
    assert isinstance(e, DataError)


def test_wallet_exists_inherits() -> None:
    """WalletExistsError inherits from DataError."""
    e = WalletExistsError("already there")
    assert isinstance(e, DataError)


def test_no_transactions_inherits() -> None:
    """NoTransactionsError inherits from DataError."""
    e = NoTransactionsError("no txns")
    assert isinstance(e, DataError)


def test_config_error_exit_code() -> None:
    """ConfigError has exit_code 5."""
    e = ConfigError("bad config")
    assert e.exit_code == 5


def test_config_missing_inherits() -> None:
    """ConfigMissingError inherits from ConfigError."""
    e = ConfigMissingError("config not found")
    assert isinstance(e, ConfigError)


def test_config_invalid_inherits() -> None:
    """ConfigInvalidError inherits from ConfigError."""
    e = ConfigInvalidError("parse error")
    assert isinstance(e, ConfigError)


def test_database_error_exit_code() -> None:
    """DatabaseError has exit_code 6."""
    e = DatabaseError("db error")
    assert e.exit_code == 6


# ── to_dict() ────────────────────────────────────────────────────────────────


def test_to_dict_structure() -> None:
    """to_dict should include error, message, details."""
    e = WhalecliError("some error", details={"key": "value"})
    d = e.to_dict()
    assert d["error"] == "unknown_error"
    assert d["message"] == "some error"
    assert d["details"]["key"] == "value"


def test_to_dict_no_details() -> None:
    """to_dict should work with no details."""
    e = APIError("api fail")
    d = e.to_dict()
    assert d["error"] == "api_error"
    assert d["details"] == {}


def test_api_error_to_dict() -> None:
    """APIError.to_dict should include the correct error_code."""
    e = InvalidAPIKeyError("key invalid")
    d = e.to_dict()
    assert d["error"] == "invalid_api_key"
