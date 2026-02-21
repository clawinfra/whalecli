"""SQLite state management for whalecli.

Manages wallet registry, transaction cache, and alert history.
"""

import sqlite3
import aiosqlite
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Wallet:
    """Wallet data model."""
    id: int
    address: str
    chain: str
    label: Optional[str]
    added_at: datetime


@dataclass
class Transaction:
    """Transaction data model."""
    tx_hash: str
    wallet_address: str
    chain: str
    timestamp: datetime
    amount_usd: float
    direction: str  # 'in' or 'out'
    raw_json: str


@dataclass
class Alert:
    """Alert data model."""
    id: int
    wallet_address: str
    score: int
    flow_usd: float
    triggered_at: datetime
    details: str


DEFAULT_DB_PATH = Path.home() / ".whalecli" / "whale.db"


def init_db(path: str = str(DEFAULT_DB_PATH)) -> sqlite3.Connection:
    """Initialize database and create tables if they don't exist.

    Args:
        path: Path to SQLite database file.

    Returns:
        SQLite connection object.
    """
    # TODO: Implement in Builder phase
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def add_wallet(address: str, chain: str, label: Optional[str] = None, db_path: str = str(DEFAULT_DB_PATH)):
    """Add a wallet to the tracking list.

    Args:
        address: Wallet address.
        chain: Blockchain (ETH, BTC, HL).
        label: Optional human-readable label.
        db_path: Path to database.
    """
    # TODO: Implement in Builder phase
    pass


def list_wallets(chain: Optional[str] = None, db_path: str = str(DEFAULT_DB_PATH)) -> List[Wallet]:
    """List all tracked wallets.

    Args:
        chain: Optional chain filter.
        db_path: Path to database.

    Returns:
        List of Wallet objects.
    """
    # TODO: Implement in Builder phase
    return []


def remove_wallet(address: str, db_path: str = str(DEFAULT_DB_PATH)):
    """Remove a wallet from the tracking list.

    Args:
        address: Wallet address to remove.
        db_path: Path to database.
    """
    # TODO: Implement in Builder phase
    pass


def cache_transaction(tx: Transaction, db_path: str = str(DEFAULT_DB_PATH)):
    """Cache a transaction to avoid duplicate API calls.

    Args:
        tx: Transaction object.
        db_path: Path to database.
    """
    # TODO: Implement in Builder phase
    pass


def get_cached_transactions(address: str, hours: int, db_path: str = str(DEFAULT_DB_PATH)) -> List[Transaction]:
    """Get cached transactions for a wallet.

    Args:
        address: Wallet address.
        hours: Time window in hours.
        db_path: Path to database.

    Returns:
        List of Transaction objects.
    """
    # TODO: Implement in Builder phase
    return []


def log_alert(alert: Alert, db_path: str = str(DEFAULT_DB_PATH)):
    """Log an alert to the database.

    Args:
        alert: Alert object.
        db_path: Path to database.
    """
    # TODO: Implement in Builder phase
    pass


def get_alert_history(limit: int = 100, db_path: str = str(DEFAULT_DB_PATH)) -> List[Alert]:
    """Get alert history.

    Args:
        limit: Maximum number of alerts to return.
        db_path: Path to database.

    Returns:
        List of Alert objects.
    """
    # TODO: Implement in Builder phase
    return []
