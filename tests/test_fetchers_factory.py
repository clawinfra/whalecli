"""Tests for whalecli/fetchers/__init__.py — factory function."""

from __future__ import annotations

import pytest

from whalecli.config import WhalecliConfig
from whalecli.fetchers import get_fetcher
from whalecli.fetchers.btc import BTCFetcher
from whalecli.fetchers.eth import EtherscanClient
from whalecli.fetchers.hl import HyperliquidClient


@pytest.fixture
def config() -> WhalecliConfig:
    return WhalecliConfig()


def test_get_fetcher_eth(config: WhalecliConfig) -> None:
    """get_fetcher('ETH') returns EtherscanClient."""
    fetcher = get_fetcher("ETH", config)
    assert isinstance(fetcher, EtherscanClient)


def test_get_fetcher_eth_lowercase(config: WhalecliConfig) -> None:
    """get_fetcher('eth') (lowercase) also returns EtherscanClient."""
    fetcher = get_fetcher("eth", config)
    assert isinstance(fetcher, EtherscanClient)


def test_get_fetcher_btc(config: WhalecliConfig) -> None:
    """get_fetcher('BTC') returns BTCFetcher."""
    fetcher = get_fetcher("BTC", config)
    assert isinstance(fetcher, BTCFetcher)


def test_get_fetcher_hl(config: WhalecliConfig) -> None:
    """get_fetcher('HL') returns HyperliquidClient."""
    fetcher = get_fetcher("HL", config)
    assert isinstance(fetcher, HyperliquidClient)


def test_get_fetcher_unknown_chain(config: WhalecliConfig) -> None:
    """get_fetcher with unknown chain raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported chain"):
        get_fetcher("SOL", config)


def test_get_fetcher_returns_protocol_compliant_object(config: WhalecliConfig) -> None:
    """All fetchers should have get_transactions, get_wallet_age, validate_address."""
    for chain in ["ETH", "BTC", "HL"]:
        fetcher = get_fetcher(chain, config)
        assert hasattr(fetcher, "get_transactions")
        assert hasattr(fetcher, "get_wallet_age")
        assert hasattr(fetcher, "validate_address")
