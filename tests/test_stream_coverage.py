"""Additional coverage tests for stream.py internal helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from whalecli.config import WhalecliConfig
from whalecli.db import Database
from whalecli.models import Transaction
from whalecli.stream import _fetch_and_score, _get_30d_avg, _poll_cycle


def _make_mock_db(wallets=None, score_history=None) -> MagicMock:
    db = MagicMock(spec=Database)
    db.list_wallets = AsyncMock(return_value=wallets or [])
    db.get_score_history = AsyncMock(return_value=score_history or [])
    db.save_score = AsyncMock()
    db.is_duplicate_alert = AsyncMock(return_value=False)
    db.save_alert = AsyncMock(return_value={"id": 1})
    db.update_alert_webhook = AsyncMock()
    return db


def _make_config() -> WhalecliConfig:
    cfg = WhalecliConfig()
    cfg.database.path = ":memory:"
    return cfg


def _make_transaction(
    to_addr: str = "0xtest",
    value_usd: float = 50_000.0,
) -> Transaction:
    return Transaction(
        tx_hash="0xtesthash",
        chain="ETH",
        from_addr="0xsender",
        to_addr=to_addr,
        timestamp=datetime.now(tz=UTC).isoformat(),
        value_native=Decimal("5.0"),
        block_num=100,
        value_usd=value_usd,
        gas_usd=5.0,
        token_symbol=None,
        token_addr=None,
        fetched_at="",
    )


# ── _get_30d_avg ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_30d_avg_no_history() -> None:
    """Returns 0.0 when no score history exists."""
    wallet = {"address": "0xtest", "chain": "ETH"}
    db = _make_mock_db(score_history=[])
    avg = await _get_30d_avg(wallet, db)
    assert avg == 0.0


@pytest.mark.asyncio
async def test_get_30d_avg_with_history() -> None:
    """Returns mean of absolute net flows from history."""
    history = [
        {"net_flow_usd": 100_000.0},
        {"net_flow_usd": -200_000.0},
        {"net_flow_usd": 300_000.0},
    ]
    wallet = {"address": "0xtest", "chain": "ETH"}
    db = _make_mock_db(score_history=history)
    avg = await _get_30d_avg(wallet, db)
    # Average of abs values: (100k + 200k + 300k) / 3 = 200k
    assert abs(avg - 200_000.0) < 1.0


# ── _fetch_and_score ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_and_score_returns_scored_wallet() -> None:
    """_fetch_and_score returns a scored wallet dict."""
    wallet = {
        "address": "0xtest_wallet",
        "chain": "ETH",
        "label": "Test",
        "tags": [],
    }

    mock_fetcher = MagicMock()
    mock_fetcher.get_transactions = AsyncMock(
        return_value=[_make_transaction(to_addr="0xtest_wallet")]
    )

    db = _make_mock_db()

    with patch("whalecli.scorer.load_exchange_addresses", return_value=set()):
        result = await _fetch_and_score(
            wallet, hours=24, fetcher=mock_fetcher, exchange_addrs=set(), db=db
        )

    assert result is not None
    assert result["address"] == "0xtest_wallet"
    assert "score" in result


@pytest.mark.asyncio
async def test_fetch_and_score_handles_fetch_exception() -> None:
    """_fetch_and_score returns scored wallet even when fetch fails (empty txns)."""
    wallet = {
        "address": "0xerror_wallet",
        "chain": "ETH",
        "label": "Error Wallet",
        "tags": [],
    }

    mock_fetcher = MagicMock()
    mock_fetcher.get_transactions = AsyncMock(side_effect=Exception("API error"))

    db = _make_mock_db()

    result = await _fetch_and_score(
        wallet, hours=24, fetcher=mock_fetcher, exchange_addrs=set(), db=db
    )
    # Returns scored wallet with empty transactions (score = 0)
    assert result is not None
    assert result["score"] == 0


# ── _poll_cycle ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_poll_cycle_empty_wallets() -> None:
    """_poll_cycle returns empty list when no wallets tracked."""
    config = _make_config()
    db = _make_mock_db(wallets=[])

    result = await _poll_cycle(chains=["ETH"], hours=1, config=config, db=db)
    assert result == []


@pytest.mark.asyncio
async def test_poll_cycle_with_wallets() -> None:
    """_poll_cycle returns scored wallets for each tracked wallet."""
    config = _make_config()
    wallets = [
        {"address": "0xcycle_wallet", "chain": "ETH", "label": "Test", "tags": [], "active": True},
    ]
    db = _make_mock_db(wallets=wallets)

    with patch("whalecli.stream.get_fetcher") as mock_get_fetcher:
        mock_fetcher = MagicMock()
        mock_fetcher.get_transactions = AsyncMock(return_value=[])
        mock_get_fetcher.return_value = mock_fetcher

        result = await _poll_cycle(chains=["ETH"], hours=1, config=config, db=db)

    assert len(result) == 1
    assert result[0]["address"] == "0xcycle_wallet"


@pytest.mark.asyncio
async def test_poll_cycle_all_chains_defaults() -> None:
    """_poll_cycle with ALL or empty chains queries ETH and BTC."""
    config = _make_config()
    db = _make_mock_db(wallets=[])

    with patch("whalecli.stream.get_fetcher") as mock_get_fetcher:
        mock_fetcher = MagicMock()
        mock_fetcher.get_transactions = AsyncMock(return_value=[])
        mock_get_fetcher.return_value = mock_fetcher

        result = await _poll_cycle(chains=["ALL"], hours=1, config=config, db=db)

    assert result == []  # No wallets, but no error


@pytest.mark.asyncio
async def test_poll_cycle_handles_fetch_errors() -> None:
    """_poll_cycle continues if a single wallet fetch errors."""
    config = _make_config()
    wallets = [
        {"address": "0xgood_wallet", "chain": "ETH", "label": "Good", "tags": [], "active": True},
    ]
    db = _make_mock_db(wallets=wallets)

    with patch("whalecli.stream.get_fetcher") as mock_get_fetcher:
        mock_fetcher = MagicMock()
        mock_fetcher.get_transactions = AsyncMock(side_effect=Exception("Network error"))
        mock_get_fetcher.return_value = mock_fetcher

        result = await _poll_cycle(chains=["ETH"], hours=1, config=config, db=db)

    # Should still return a scored wallet (with empty transactions)
    assert len(result) == 1
    assert result[0]["score"] == 0
