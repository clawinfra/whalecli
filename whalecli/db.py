"""SQLite state management for whalecli.

Manages wallet registry, transaction cache, alert history, and alert rules.
All database operations are async (aiosqlite).

Schema:
  - wallets: tracked whale wallet registry
  - transactions: raw tx cache (TTL-based)
  - scores: whale score snapshots
  - alerts: triggered alert log
  - alert_rules: user-configured alert rules
  - exchange_addresses: known exchange hot/cold wallet registry
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from whalecli.exceptions import DatabaseError, WalletExistsError, WalletNotFoundError

DEFAULT_DB_PATH = Path.home() / ".whalecli" / "whale.db"

# SQL schema — applied on connect if tables don't exist
_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS wallets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    address      TEXT NOT NULL,
    chain        TEXT NOT NULL CHECK (chain IN ('ETH', 'BTC', 'HL')),
    label        TEXT NOT NULL DEFAULT '',
    tags         TEXT NOT NULL DEFAULT '[]',
    added_at     TEXT NOT NULL,
    first_seen   TEXT,
    active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(address, chain)
);

CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chain        TEXT NOT NULL,
    tx_hash      TEXT NOT NULL,
    block_num    INTEGER,
    timestamp    TEXT NOT NULL,
    from_addr    TEXT NOT NULL,
    to_addr      TEXT NOT NULL,
    value_native TEXT NOT NULL,
    value_usd    REAL,
    gas_usd      REAL,
    token_symbol TEXT,
    token_addr   TEXT,
    fetched_at   TEXT NOT NULL,
    UNIQUE(chain, tx_hash)
);

CREATE TABLE IF NOT EXISTS scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    address       TEXT NOT NULL,
    chain         TEXT NOT NULL,
    computed_at   TEXT NOT NULL,
    window_hours  INTEGER NOT NULL,
    total_score   INTEGER NOT NULL,
    net_flow      INTEGER NOT NULL,
    velocity      INTEGER NOT NULL,
    correlation   INTEGER NOT NULL,
    exchange_flow INTEGER NOT NULL,
    net_flow_usd  REAL,
    direction     TEXT CHECK (direction IN ('accumulating', 'distributing', 'neutral')),
    alert_triggered INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alerts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    address        TEXT NOT NULL,
    chain          TEXT NOT NULL,
    label          TEXT NOT NULL DEFAULT '',
    score          INTEGER NOT NULL,
    direction      TEXT NOT NULL,
    net_flow_usd   REAL NOT NULL DEFAULT 0,
    triggered_at   TEXT NOT NULL,
    rule_id        TEXT NOT NULL DEFAULT '',
    webhook_sent   INTEGER NOT NULL DEFAULT 0,
    webhook_status INTEGER
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL CHECK (type IN ('score', 'flow')),
    value       REAL NOT NULL,
    window      TEXT NOT NULL DEFAULT '1h',
    chain       TEXT,
    webhook_url TEXT,
    created_at  TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS api_cache (
    cache_key    TEXT PRIMARY KEY,
    response     TEXT NOT NULL,
    fetched_at   REAL NOT NULL,
    ttl_seconds  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wallets_chain ON wallets(chain);
CREATE INDEX IF NOT EXISTS idx_transactions_chain_ts ON transactions(chain, timestamp);
CREATE INDEX IF NOT EXISTS idx_transactions_from ON transactions(from_addr);
CREATE INDEX IF NOT EXISTS idx_transactions_to ON transactions(to_addr);
CREATE INDEX IF NOT EXISTS idx_scores_addr ON scores(address, chain);
CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts(triggered_at);
"""

SCHEMA_VERSION = 1


class Database:
    """
    Async SQLite database manager for whalecli.

    Usage:
        db = Database(":memory:")
        await db.connect()
        wallets = await db.list_wallets()
        await db.close()

    Or as async context manager:
        async with Database(path) as db:
            ...
    """

    def __init__(self, db_path: str = str(DEFAULT_DB_PATH)) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open DB connection and run schema migrations."""
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA foreign_keys=ON")
            await self._apply_schema()
        except Exception as e:
            raise DatabaseError(f"Failed to connect to database: {e}") from e

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ──────────────────────────────────────────────────────────
    # Wallet management
    # ──────────────────────────────────────────────────────────

    async def add_wallet(
        self,
        address: str,
        chain: str,
        label: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Add a wallet to the tracking registry.

        Returns the created wallet dict.
        Raises WalletExistsError if the address+chain combo already exists.
        """
        assert self._conn is not None
        chain = chain.upper()
        tags_json = json.dumps(tags or [])
        added_at = datetime.now(tz=timezone.utc).isoformat()

        try:
            async with self._conn.execute(
                """
                INSERT INTO wallets (address, chain, label, tags, added_at, active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (address, chain, label, tags_json, added_at),
            ) as cursor:
                row_id = cursor.lastrowid
            await self._conn.commit()
        except aiosqlite.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise WalletExistsError(
                    f"Address {address[:8]}...{address[-5:]} on {chain} is already tracked",
                    details={"address": address, "chain": chain},
                ) from e
            raise DatabaseError(f"Failed to add wallet: {e}") from e

        return {
            "id": row_id,
            "address": address,
            "chain": chain,
            "label": label,
            "tags": tags or [],
            "added_at": added_at,
            "first_seen": None,
            "active": True,
        }

    async def list_wallets(
        self,
        chain: str | None = None,
        tags: list[str] | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """List tracked wallets with optional filters."""
        assert self._conn is not None

        query = "SELECT * FROM wallets"
        params: list[Any] = []
        conditions: list[str] = []

        if active_only:
            conditions.append("active = 1")
        if chain:
            conditions.append("chain = ?")
            params.append(chain.upper())

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY added_at DESC"

        wallets = []
        async with self._conn.execute(query, params) as cursor:
            async for row in cursor:
                w = dict(row)
                w["tags"] = json.loads(w.get("tags") or "[]")
                w["active"] = bool(w["active"])
                wallets.append(w)

        # Filter by tags in Python (SQLite JSON support is limited)
        if tags:
            wallets = [w for w in wallets if any(t in w["tags"] for t in tags)]

        return wallets

    async def get_wallet(self, address: str, chain: str | None = None) -> dict[str, Any]:
        """
        Get a wallet by address.

        Raises WalletNotFoundError if not found.
        """
        assert self._conn is not None

        query = "SELECT * FROM wallets WHERE address = ? AND active = 1"
        params: list[Any] = [address]
        if chain:
            query += " AND chain = ?"
            params.append(chain.upper())

        async with self._conn.execute(query, params) as cursor:
            row = await cursor.fetchone()

        if not row:
            raise WalletNotFoundError(
                f"Wallet {address} not found",
                details={"address": address, "chain": chain},
            )

        w = dict(row)
        w["tags"] = json.loads(w.get("tags") or "[]")
        w["active"] = bool(w["active"])
        return w

    async def remove_wallet(self, address: str, chain: str, purge: bool = False) -> dict[str, Any]:
        """
        Mark wallet inactive (soft delete) or purge it entirely.

        Returns info about what was removed.
        """
        assert self._conn is not None

        # Check it exists
        await self.get_wallet(address, chain)

        if purge:
            # Delete all cached transactions for this wallet
            async with self._conn.execute(
                "DELETE FROM transactions WHERE (from_addr = ? OR to_addr = ?) AND chain = ?",
                (address.lower(), address.lower(), chain.upper()),
            ) as cursor:
                tx_deleted = cursor.rowcount
            await self._conn.execute(
                "DELETE FROM wallets WHERE address = ? AND chain = ?",
                (address, chain.upper()),
            )
        else:
            tx_deleted = 0
            await self._conn.execute(
                "UPDATE wallets SET active = 0 WHERE address = ? AND chain = ?",
                (address, chain.upper()),
            )

        await self._conn.commit()
        result: dict[str, Any] = {
            "status": "removed",
            "address": address,
            "chain": chain.upper(),
        }
        if purge:
            result["transactions_deleted"] = tx_deleted
        return result

    async def update_wallet_first_seen(self, address: str, chain: str, first_seen: str) -> None:
        """Update the first_seen timestamp for a wallet."""
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE wallets SET first_seen = ? WHERE address = ? AND chain = ?",
            (first_seen, address, chain.upper()),
        )
        await self._conn.commit()

    async def import_wallets(
        self, wallets_data: list[dict[str, Any]], dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Bulk import wallets from a list of dicts.

        Returns summary: {imported, skipped, errors, wallets}
        """
        imported = 0
        skipped = 0
        errors: list[str] = []
        added_wallets = []

        for item in wallets_data:
            address = item.get("address", "")
            chain = item.get("chain", "")
            label = item.get("label", "")
            tags_raw = item.get("tags", "")
            tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()] if tags_raw else []

            if not address or not chain:
                errors.append(f"Missing address or chain: {item}")
                continue

            if dry_run:
                # Just count it
                imported += 1
                continue

            try:
                w = await self.add_wallet(address, chain, label, tags)
                imported += 1
                added_wallets.append(w)
            except WalletExistsError:
                skipped += 1
            except Exception as e:
                errors.append(str(e))

        if dry_run:
            return {
                "would_import": imported,
                "would_skip": skipped,
                "validation_errors": errors,
            }

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "wallets": added_wallets,
        }

    # ──────────────────────────────────────────────────────────
    # Transaction cache
    # ──────────────────────────────────────────────────────────

    async def upsert_transactions(self, transactions: list[dict[str, Any]]) -> int:
        """
        Insert or replace transactions in the cache.

        Returns number of rows inserted/updated.
        """
        assert self._conn is not None
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        count = 0

        for tx in transactions:
            try:
                await self._conn.execute(
                    """
                    INSERT OR REPLACE INTO transactions
                    (chain, tx_hash, block_num, timestamp, from_addr, to_addr,
                     value_native, value_usd, gas_usd, token_symbol, token_addr, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tx.get("chain", ""),
                        tx.get("tx_hash", ""),
                        tx.get("block_num"),
                        tx.get("timestamp", ""),
                        tx.get("from_addr", ""),
                        tx.get("to_addr", ""),
                        str(tx.get("value_native", 0)),
                        tx.get("value_usd"),
                        tx.get("gas_usd"),
                        tx.get("token_symbol"),
                        tx.get("token_addr"),
                        now_iso,
                    ),
                )
                count += 1
            except aiosqlite.Error:
                pass  # Skip bad rows

        await self._conn.commit()
        return count

    async def get_cached_transactions(
        self,
        address: str,
        chain: str,
        from_ts: str,
        to_ts: str,
        ttl_hours: int = 24,
    ) -> list[dict[str, Any]] | None:
        """
        Get cached transactions for a wallet in a time range.

        Returns None if cache is expired or missing (caller should refetch).
        Returns list (possibly empty) if cache is fresh.
        """
        assert self._conn is not None

        cutoff_fetch = datetime.now(tz=timezone.utc).timestamp() - (ttl_hours * 3600)
        cutoff_fetch_iso = datetime.fromtimestamp(cutoff_fetch, tz=timezone.utc).isoformat()

        # Check if we have ANY fresh records for this address+chain
        async with self._conn.execute(
            """
            SELECT COUNT(*) as cnt FROM transactions
            WHERE chain = ?
            AND (from_addr = ? OR to_addr = ?)
            AND fetched_at > ?
            """,
            (chain.upper(), address.lower(), address.lower(), cutoff_fetch_iso),
        ) as cursor:
            row = await cursor.fetchone()
            if not row or row["cnt"] == 0:
                return None  # Cache miss

        # Return fresh cached records in time range
        rows = []
        async with self._conn.execute(
            """
            SELECT * FROM transactions
            WHERE chain = ?
            AND (from_addr = ? OR to_addr = ?)
            AND timestamp >= ?
            AND timestamp <= ?
            ORDER BY timestamp DESC
            """,
            (chain.upper(), address.lower(), address.lower(), from_ts, to_ts),
        ) as cursor:
            async for row in cursor:
                rows.append(dict(row))

        return rows

    # ──────────────────────────────────────────────────────────
    # Score snapshots
    # ──────────────────────────────────────────────────────────

    async def save_score(self, score_data: dict[str, Any]) -> None:
        """Persist a whale score snapshot."""
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT INTO scores
            (address, chain, computed_at, window_hours, total_score,
             net_flow, velocity, correlation, exchange_flow,
             net_flow_usd, direction, alert_triggered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score_data.get("address", ""),
                score_data.get("chain", ""),
                score_data.get("computed_at", ""),
                score_data.get("window_hours", 24),
                score_data.get("total", 0),
                score_data.get("net_flow", 0),
                score_data.get("velocity", 0),
                score_data.get("correlation", 0),
                score_data.get("exchange_flow", 0),
                score_data.get("net_flow_usd", 0.0),
                score_data.get("direction", "neutral"),
                1 if score_data.get("alert_triggered") else 0,
            ),
        )
        await self._conn.commit()

    async def get_score_history(
        self,
        address: str,
        chain: str,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get score history for a wallet over N days."""
        assert self._conn is not None
        cutoff = datetime.now(tz=timezone.utc).timestamp() - (days * 86400)
        cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()

        rows = []
        async with self._conn.execute(
            """
            SELECT * FROM scores
            WHERE address = ? AND chain = ?
            AND computed_at >= ?
            ORDER BY computed_at DESC
            """,
            (address, chain.upper(), cutoff_iso),
        ) as cursor:
            async for row in cursor:
                rows.append(dict(row))

        return rows

    # ──────────────────────────────────────────────────────────
    # Alerts
    # ──────────────────────────────────────────────────────────

    async def save_alert(self, alert_data: dict[str, Any]) -> dict[str, Any]:
        """Persist an alert event. Returns alert with generated id."""
        assert self._conn is not None
        triggered_at = alert_data.get("triggered_at", datetime.now(tz=timezone.utc).isoformat())

        async with self._conn.execute(
            """
            INSERT INTO alerts
            (address, chain, label, score, direction, net_flow_usd,
             triggered_at, rule_id, webhook_sent, webhook_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert_data.get("address", ""),
                alert_data.get("chain", ""),
                alert_data.get("label", ""),
                alert_data.get("score", 0),
                alert_data.get("direction", "neutral"),
                alert_data.get("net_flow_usd", 0.0),
                triggered_at,
                alert_data.get("rule_id", ""),
                1 if alert_data.get("webhook_sent") else 0,
                alert_data.get("webhook_status"),
            ),
        ) as cursor:
            row_id = cursor.lastrowid

        await self._conn.commit()
        result = dict(alert_data)
        result["id"] = row_id
        return result

    async def list_alerts(
        self,
        chain: str | None = None,
        limit: int = 20,
        since_hours: int | None = None,
    ) -> list[dict[str, Any]]:
        """List recent alerts with optional filters."""
        assert self._conn is not None

        query = "SELECT * FROM alerts"
        params: list[Any] = []
        conditions: list[str] = []

        if chain:
            conditions.append("chain = ?")
            params.append(chain.upper())

        if since_hours:
            cutoff = datetime.now(tz=timezone.utc).timestamp() - (since_hours * 3600)
            cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
            conditions.append("triggered_at >= ?")
            params.append(cutoff_iso)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY triggered_at DESC LIMIT ?"
        params.append(limit)

        rows = []
        async with self._conn.execute(query, params) as cursor:
            async for row in cursor:
                d = dict(row)
                d["webhook_sent"] = bool(d["webhook_sent"])
                rows.append(d)

        return rows

    async def is_duplicate_alert(
        self, address: str, chain: str, window_seconds: int = 3600
    ) -> bool:
        """
        Check if this wallet already triggered an alert in the current window.
        """
        assert self._conn is not None
        cutoff_ts = time.time() - window_seconds
        cutoff_iso = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).isoformat()

        async with self._conn.execute(
            """
            SELECT COUNT(*) as cnt FROM alerts
            WHERE address = ? AND chain = ? AND triggered_at >= ?
            """,
            (address, chain.upper(), cutoff_iso),
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row and row["cnt"] > 0)

    async def update_alert_webhook(
        self, alert_id: int, webhook_sent: bool, webhook_status: int | None
    ) -> None:
        """Update webhook delivery status for an alert."""
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE alerts SET webhook_sent = ?, webhook_status = ? WHERE id = ?",
            (1 if webhook_sent else 0, webhook_status, alert_id),
        )
        await self._conn.commit()

    # ──────────────────────────────────────────────────────────
    # Alert Rules
    # ──────────────────────────────────────────────────────────

    async def save_alert_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Save an alert rule."""
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT OR REPLACE INTO alert_rules
            (id, type, value, window, chain, webhook_url, created_at, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule["id"],
                rule["type"],
                rule["value"],
                rule.get("window", "1h"),
                rule.get("chain"),
                rule.get("webhook_url"),
                rule.get("created_at", datetime.now(tz=timezone.utc).isoformat()),
                1 if rule.get("active", True) else 0,
            ),
        )
        await self._conn.commit()
        return rule

    async def list_alert_rules(self) -> list[dict[str, Any]]:
        """List all active alert rules."""
        assert self._conn is not None
        rows = []
        async with self._conn.execute(
            "SELECT * FROM alert_rules WHERE active = 1 ORDER BY created_at DESC"
        ) as cursor:
            async for row in cursor:
                d = dict(row)
                d["active"] = bool(d["active"])
                rows.append(d)
        return rows

    async def get_next_rule_id(self) -> str:
        """Generate the next sequential rule ID."""
        assert self._conn is not None
        async with self._conn.execute("SELECT COUNT(*) as cnt FROM alert_rules") as cursor:
            row = await cursor.fetchone()
            n = (row["cnt"] if row else 0) + 1
        return f"rule_{n:03d}"

    # ──────────────────────────────────────────────────────────
    # API Cache
    # ──────────────────────────────────────────────────────────

    async def cache_get(self, cache_key: str) -> str | None:
        """
        Return cached API response if fresh, None otherwise.
        """
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT response, fetched_at, ttl_seconds FROM api_cache WHERE cache_key = ?",
            (cache_key,),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None

        expires_at = row["fetched_at"] + row["ttl_seconds"]
        if time.time() > expires_at:
            return None  # Expired

        return row["response"]

    async def cache_set(self, cache_key: str, response: str, ttl_seconds: int) -> None:
        """Store API response in cache."""
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT OR REPLACE INTO api_cache (cache_key, response, fetched_at, ttl_seconds)
            VALUES (?, ?, ?, ?)
            """,
            (cache_key, response, time.time(), ttl_seconds),
        )
        await self._conn.commit()

    async def cache_prune(self) -> int:
        """Delete expired cache entries. Returns number deleted."""
        assert self._conn is not None
        async with self._conn.execute(
            "DELETE FROM api_cache WHERE fetched_at + ttl_seconds < ?",
            (time.time(),),
        ) as cursor:
            deleted = cursor.rowcount
        await self._conn.commit()
        return deleted

    # ──────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────

    async def _apply_schema(self) -> None:
        """Apply schema migrations idempotently."""
        assert self._conn is not None
        await self._conn.executescript(_SCHEMA)
        await self._conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        await self._conn.commit()
