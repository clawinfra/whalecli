"""Pytest fixtures shared across all whalecli tests."""

from __future__ import annotations

import asyncio
import pytest

from whalecli.config import (
    AlertConfig,
    APIConfig,
    CloudConfig,
    DatabaseConfig,
    OutputConfig,
    WhalecliConfig,
)
from whalecli.db import Database
from whalecli.fetchers.base import RawTransaction
from whalecli.models import Transaction
from decimal import Decimal
from datetime import datetime, timezone


# ── Config fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def sample_config() -> WhalecliConfig:
    """Minimal valid WhalecliConfig for tests."""
    return WhalecliConfig(
        api=APIConfig(
            etherscan_api_key="test_etherscan_key_12345",
            blockchain_info_api_key="",
            hyperliquid_api_key="",
        ),
        alert=AlertConfig(
            score_threshold=70,
            flow_threshold_usd=1_000_000.0,
            window_minutes=60,
            webhook_url="",
            webhook_secret="",
        ),
        database=DatabaseConfig(
            path=":memory:",
            cache_ttl_hours=24,
        ),
        output=OutputConfig(
            default_format="json",
            timezone="UTC",
            color=False,
        ),
        cloud=CloudConfig(enabled=False),
    )


@pytest.fixture
def sample_config_with_webhook(sample_config: WhalecliConfig) -> WhalecliConfig:
    """Config with a webhook URL set."""
    sample_config.alert.webhook_url = "https://hooks.example.com/whale"
    return sample_config


# ── DB fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
async def in_memory_db() -> Database:
    """In-memory SQLite DB with schema applied."""
    db = Database(":memory:")
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
def in_memory_db_sync() -> Database:
    """Synchronous wrapper around in-memory DB (for non-async tests)."""
    async def _create():
        db = Database(":memory:")
        await db.connect()
        return db

    db = asyncio.get_event_loop().run_until_complete(_create())
    yield db
    asyncio.get_event_loop().run_until_complete(db.close())


# ── Model fixtures ────────────────────────────────────────────────────────────


ETH_ADDR_1 = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
ETH_ADDR_2 = "0x28c6c06298d514db089934071355e5743bf21d60"  # Binance hot wallet
BTC_ADDR_1 = "1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf Na".replace(" ", "").replace("Na", "Na")
BTC_ADDR_VALID = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"


@pytest.fixture
def sample_eth_transactions() -> list[Transaction]:
    """10 ETH transactions with known values for scoring tests."""
    ts_base = int(datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    txns = []

    # 5 inflows (large accumulation signal)
    for i in range(5):
        txns.append(Transaction(
            tx_hash=f"0xin{i:04d}abcdef",
            chain="ETH",
            from_addr="0xsome_whale_sender",
            to_addr=ETH_ADDR_1,
            timestamp=datetime.fromtimestamp(ts_base + i * 3600, tz=timezone.utc).isoformat(),
            value_native=Decimal("10.0"),  # 10 ETH each
            block_num=18_000_000 + i,
            value_usd=30_000.0,  # $30k each
            gas_usd=5.0,
            token_symbol=None,
            token_addr=None,
            fetched_at="",
        ))

    # 5 outflows (smaller)
    for i in range(5):
        txns.append(Transaction(
            tx_hash=f"0xout{i:04d}abcdef",
            chain="ETH",
            from_addr=ETH_ADDR_1,
            to_addr="0xsome_recipient",
            timestamp=datetime.fromtimestamp(ts_base + (i + 5) * 3600, tz=timezone.utc).isoformat(),
            value_native=Decimal("2.0"),
            block_num=18_000_100 + i,
            value_usd=6_000.0,
            gas_usd=5.0,
            token_symbol=None,
            token_addr=None,
            fetched_at="",
        ))

    return txns


@pytest.fixture
def sample_btc_transactions() -> list[Transaction]:
    """5 BTC transactions."""
    ts_base = int(datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    txns = []
    for i in range(5):
        txns.append(Transaction(
            tx_hash=f"btc_tx_hash_{i:04d}",
            chain="BTC",
            from_addr="multiple",
            to_addr=BTC_ADDR_VALID,
            timestamp=datetime.fromtimestamp(ts_base + i * 3600, tz=timezone.utc).isoformat(),
            value_native=Decimal("0.5"),
            block_num=800_000 + i,
            value_usd=25_000.0,
            gas_usd=2.0,
            token_symbol=None,
            token_addr=None,
            fetched_at="",
        ))
    return txns


@pytest.fixture
def large_inflow_transactions() -> list[Transaction]:
    """Transactions representing a large inflow ($10M+)."""
    ts = datetime(2026, 2, 22, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    return [
        Transaction(
            tx_hash=f"0xlarge{i:04d}",
            chain="ETH",
            from_addr="0xexchange_sender",
            to_addr=ETH_ADDR_1,
            timestamp=ts,
            value_native=Decimal("1000.0"),
            block_num=18_000_200 + i,
            value_usd=3_000_000.0,
            gas_usd=10.0,
            token_symbol=None,
            token_addr=None,
            fetched_at="",
        )
        for i in range(4)  # 4 × $3M = $12M total inflow
    ]


@pytest.fixture
def mock_etherscan_response() -> dict:
    """Realistic Etherscan API response for a normal ETH transaction."""
    return {
        "status": "1",
        "message": "OK",
        "result": [
            {
                "hash": "0xabc123def456",
                "blockNumber": "18000001",
                "timeStamp": "1706906640",
                "from": "0xsender_addr",
                "to": ETH_ADDR_1,
                "value": "10000000000000000000",  # 10 ETH in wei
                "gasPrice": "20000000000",
                "gasUsed": "21000",
                "isError": "0",
                "txreceipt_status": "1",
            }
        ],
    }


@pytest.fixture
def mock_etherscan_empty() -> dict:
    """Etherscan response for an address with no transactions."""
    return {
        "status": "0",
        "message": "No transactions found",
        "result": [],
    }


@pytest.fixture
def mock_etherscan_ratelimit() -> dict:
    """Etherscan response when rate limited."""
    return {
        "status": "0",
        "message": "NOTOK",
        "result": "Max rate limit reached",
    }


@pytest.fixture
def mock_mempool_response() -> list:
    """Mempool.space API response for BTC address."""
    return [
        {
            "txid": "btc_mempool_hash_0001",
            "fee": 1000,
            "status": {
                "confirmed": True,
                "block_height": 820000,
                "block_time": 1706906640,
            },
            "vin": [],
            "vout": [
                {
                    "scriptpubkey_address": BTC_ADDR_VALID,
                    "value": 5000000,  # 0.05 BTC in satoshis
                }
            ],
        }
    ]
