"""Pytest fixtures for whalecli tests."""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime
from whalecli.config import Config, AlertConfig, DatabaseConfig, ApiConfig, OutputConfig
from whalecli.db import Wallet, Transaction


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    # Create tables
    conn.execute("""
        CREATE TABLE wallets (
            id INTEGER PRIMARY KEY,
            address TEXT NOT NULL,
            chain TEXT NOT NULL,
            label TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE transactions (
            tx_hash TEXT PRIMARY KEY,
            wallet_address TEXT NOT NULL,
            chain TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            amount_usd REAL,
            direction TEXT,
            raw_json TEXT,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE alerts (
            id INTEGER PRIMARY KEY,
            wallet_address TEXT NOT NULL,
            score INTEGER,
            flow_usd REAL,
            triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT
        )
    """)

    conn.commit()

    yield conn, path

    conn.close()
    import os
    os.close(fd)
    os.unlink(path)


@pytest.fixture
def mock_config():
    """Create a mock config object."""
    return Config(
        api=ApiConfig(
            etherscan_api_key="test_key",
            blockchain_info_api_key=""
        ),
        alert=AlertConfig(
            score_threshold=70,
            flow_threshold_usd=1_000_000,
            window_minutes=60,
            webhook_url=""
        ),
        database=DatabaseConfig(
            path=":memory:",
            cache_ttl_hours=24
        ),
        output=OutputConfig(
            default_format="json",
            timezone="UTC"
        )
    )


@pytest.fixture
def sample_wallets():
    """Sample wallet data for testing."""
    return [
        Wallet(
            id=1,
            address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            chain="ETH",
            label="Binance Cold",
            added_at=datetime(2026, 2, 22, 9, 44, 0)
        ),
        Wallet(
            id=2,
            address="bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
            chain="BTC",
            label="Unknown Whale",
            added_at=datetime(2026, 2, 22, 9, 45, 0)
        )
    ]


@pytest.fixture
def sample_transactions():
    """Sample transaction data for testing."""
    return [
        Transaction(
            tx_hash="0xabc123",
            wallet_address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            chain="ETH",
            timestamp=datetime(2026, 2, 22, 9, 44, 0),
            amount_usd=10_000_000,
            direction="in",
            raw_json='{"hash": "0xabc123"}'
        ),
        Transaction(
            tx_hash="0xdef456",
            wallet_address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            chain="ETH",
            timestamp=datetime(2026, 2, 22, 10, 0, 0),
            amount_usd=5_000_000,
            direction="out",
            raw_json='{"hash": "0xdef456"}'
        )
    ]


@pytest.fixture
def mock_etherscan_response():
    """Mock Etherscan API response."""
    return {
        "status": "1",
        "message": "OK",
        "result": [
            {
                "hash": "0xabc123",
                "from": "0xold",
                "to": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
                "value": "10000000000000000000",  # 10 ETH
                "timeStamp": "1706906640"
            }
        ]
    }


@pytest.fixture
def eth_prices():
    """Mock ETH price data."""
    return {
        "ETH": {
            "usd": 3000.0,
            "usd_24h_change": 2.5
        }
    }


@pytest.fixture
def btc_prices():
    """Mock BTC price data."""
    return {
        "BTC": {
            "usd": 50000.0,
            "usd_24h_change": 1.8
        }
    }
