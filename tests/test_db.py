"""Tests for whalecli/db.py — SQLite state management."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio

from whalecli.db import Database
from whalecli.exceptions import WalletExistsError, WalletNotFoundError


@pytest_asyncio.fixture
async def db() -> Database:
    """Fresh in-memory database for each test."""
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


# ── Schema / connection ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_creates_schema(db: Database) -> None:
    """connect() should apply schema without errors."""
    wallets = await db.list_wallets()
    assert wallets == []


@pytest.mark.asyncio
async def test_context_manager(tmp_path) -> None:
    """Database works as async context manager."""
    db_path = str(tmp_path / "test.db")
    async with Database(db_path) as db:
        wallets = await db.list_wallets()
        assert wallets == []


# ── Wallet CRUD ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_wallet(db: Database) -> None:
    """add_wallet should persist wallet and return dict."""
    result = await db.add_wallet("0xabc123", "ETH", "Whale #1")
    assert result["address"] == "0xabc123"
    assert result["chain"] == "ETH"
    assert result["label"] == "Whale #1"
    assert result["active"] is True
    assert "id" in result
    assert "added_at" in result


@pytest.mark.asyncio
async def test_add_wallet_with_tags(db: Database) -> None:
    """add_wallet should persist tags as a JSON list."""
    result = await db.add_wallet("0xdef456", "ETH", "Exchange", ["exchange", "binance"])
    assert result["tags"] == ["exchange", "binance"]


@pytest.mark.asyncio
async def test_add_wallet_duplicate_raises(db: Database) -> None:
    """Adding the same address+chain twice raises WalletExistsError."""
    await db.add_wallet("0xaaa111", "ETH", "First")
    with pytest.raises(WalletExistsError):
        await db.add_wallet("0xaaa111", "ETH", "Duplicate")


@pytest.mark.asyncio
async def test_add_wallet_same_addr_different_chain(db: Database) -> None:
    """Same address on different chains is allowed."""
    await db.add_wallet("0xaaa111", "ETH", "ETH Wallet")
    result = await db.add_wallet("0xaaa111", "HL", "HL Wallet")
    assert result["chain"] == "HL"


@pytest.mark.asyncio
async def test_list_wallets_empty(db: Database) -> None:
    """list_wallets on empty DB returns empty list."""
    wallets = await db.list_wallets()
    assert wallets == []


@pytest.mark.asyncio
async def test_list_wallets_returns_all(db: Database) -> None:
    """list_wallets returns all active wallets."""
    await db.add_wallet("0xaaa", "ETH", "A")
    await db.add_wallet("0xbbb", "ETH", "B")
    await db.add_wallet("0xccc", "BTC", "C")

    wallets = await db.list_wallets()
    assert len(wallets) == 3


@pytest.mark.asyncio
async def test_list_wallets_filter_chain(db: Database) -> None:
    """list_wallets with chain filter returns only matching wallets."""
    await db.add_wallet("0xaaa", "ETH", "ETH A")
    await db.add_wallet("0xbbb", "BTC", "BTC B")

    eth_wallets = await db.list_wallets(chain="ETH")
    assert len(eth_wallets) == 1
    assert eth_wallets[0]["chain"] == "ETH"


@pytest.mark.asyncio
async def test_get_wallet_found(db: Database) -> None:
    """get_wallet returns matching wallet dict."""
    await db.add_wallet("0xfoo123", "ETH", "Foo Whale")
    w = await db.get_wallet("0xfoo123", "ETH")
    assert w["address"] == "0xfoo123"


@pytest.mark.asyncio
async def test_get_wallet_not_found(db: Database) -> None:
    """get_wallet raises WalletNotFoundError for unknown address."""
    with pytest.raises(WalletNotFoundError):
        await db.get_wallet("0xnotexist", "ETH")


@pytest.mark.asyncio
async def test_remove_wallet_soft_delete(db: Database) -> None:
    """remove_wallet (no purge) marks wallet inactive."""
    await db.add_wallet("0xremove_me", "ETH", "Remove")
    await db.remove_wallet("0xremove_me", "ETH")

    wallets = await db.list_wallets(active_only=True)
    addrs = [w["address"] for w in wallets]
    assert "0xremove_me" not in addrs


@pytest.mark.asyncio
async def test_remove_wallet_not_found(db: Database) -> None:
    """remove_wallet raises WalletNotFoundError for unknown address."""
    with pytest.raises(WalletNotFoundError):
        await db.remove_wallet("0xghostaddr", "ETH")


@pytest.mark.asyncio
async def test_import_wallets(db: Database) -> None:
    """import_wallets should bulk-insert wallets."""
    rows = [
        {"address": "0xaaa", "chain": "ETH", "label": "A"},
        {"address": "0xbbb", "chain": "BTC", "label": "B"},
        {"address": "0xccc", "chain": "ETH", "label": "C"},
    ]
    result = await db.import_wallets(rows)
    assert result["imported"] == 3
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_import_wallets_dry_run(db: Database) -> None:
    """import_wallets dry_run should not persist anything."""
    rows = [{"address": "0xddd", "chain": "ETH", "label": "D"}]
    result = await db.import_wallets(rows, dry_run=True)
    assert result["would_import"] == 1

    wallets = await db.list_wallets()
    assert len(wallets) == 0  # nothing actually added


# ── Transactions cache ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_transactions(db: Database) -> None:
    """upsert_transactions should insert and return count."""
    txns = [
        {
            "chain": "ETH",
            "tx_hash": "0xhash1",
            "block_num": 100,
            "timestamp": "2026-02-22T10:00:00+00:00",
            "from_addr": "0xsender",
            "to_addr": "0xrecipient",
            "value_native": "1.5",
            "value_usd": 4500.0,
            "gas_usd": 5.0,
        },
        {
            "chain": "ETH",
            "tx_hash": "0xhash2",
            "block_num": 101,
            "timestamp": "2026-02-22T10:05:00+00:00",
            "from_addr": "0xrecipient",
            "to_addr": "0xsender",
            "value_native": "0.5",
            "value_usd": 1500.0,
            "gas_usd": 5.0,
        },
    ]
    count = await db.upsert_transactions(txns)
    assert count == 2


@pytest.mark.asyncio
async def test_upsert_transactions_dedup(db: Database) -> None:
    """Inserting the same tx_hash+chain twice should not error (idempotent)."""
    tx = {
        "chain": "ETH",
        "tx_hash": "0xduptx",
        "block_num": 200,
        "timestamp": "2026-02-22T11:00:00+00:00",
        "from_addr": "0xa",
        "to_addr": "0xb",
        "value_native": "1.0",
    }
    await db.upsert_transactions([tx])
    count = await db.upsert_transactions([tx])  # second insert should succeed
    assert count == 1


# ── Scores ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_and_get_score_history(db: Database) -> None:
    """save_score and get_score_history round-trip."""
    score = {
        "address": "0xscored_addr",
        "chain": "ETH",
        "computed_at": datetime.now(tz=UTC).isoformat(),
        "window_hours": 24,
        "total": 82,
        "net_flow": 35,
        "velocity": 20,
        "correlation": 15,
        "exchange_flow": 12,
        "net_flow_usd": 8_000_000.0,
        "direction": "accumulating",
        "alert_triggered": True,
    }
    await db.save_score(score)

    history = await db.get_score_history("0xscored_addr", "ETH", days=7)
    assert len(history) == 1
    assert history[0]["total_score"] == 82


# ── Alerts ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_alert(db: Database) -> None:
    """save_alert persists an alert and returns with id."""
    alert = {
        "address": "0xalert_wallet",
        "chain": "ETH",
        "label": "Test Whale",
        "score": 85,
        "direction": "accumulating",
        "net_flow_usd": 5_000_000.0,
        "triggered_at": datetime.now(tz=UTC).isoformat(),
        "rule_id": "rule_001",
    }
    saved = await db.save_alert(alert)
    assert saved["id"] is not None
    assert saved["score"] == 85


@pytest.mark.asyncio
async def test_list_alerts(db: Database) -> None:
    """list_alerts returns persisted alerts."""
    alert = {
        "address": "0xalert_wallet",
        "chain": "ETH",
        "label": "Whale",
        "score": 90,
        "direction": "distributing",
        "net_flow_usd": -3_000_000.0,
        "triggered_at": datetime.now(tz=UTC).isoformat(),
        "rule_id": "auto",
    }
    await db.save_alert(alert)
    alerts = await db.list_alerts(limit=10)
    assert len(alerts) >= 1
    assert alerts[0]["score"] == 90


@pytest.mark.asyncio
async def test_is_duplicate_alert_within_window(db: Database) -> None:
    """is_duplicate_alert returns True for same wallet within dedup window."""
    alert = {
        "address": "0xdup_wallet",
        "chain": "ETH",
        "label": "",
        "score": 80,
        "direction": "neutral",
        "net_flow_usd": 0.0,
        "triggered_at": datetime.now(tz=UTC).isoformat(),
        "rule_id": "auto",
    }
    await db.save_alert(alert)
    is_dup = await db.is_duplicate_alert("0xdup_wallet", "ETH", window_seconds=3600)
    assert is_dup is True


@pytest.mark.asyncio
async def test_is_not_duplicate_outside_window(db: Database) -> None:
    """is_duplicate_alert returns False when outside dedup window."""
    alert = {
        "address": "0xold_alert",
        "chain": "ETH",
        "label": "",
        "score": 75,
        "direction": "neutral",
        "net_flow_usd": 0.0,
        "triggered_at": "2020-01-01T00:00:00+00:00",  # old timestamp
        "rule_id": "auto",
    }
    await db.save_alert(alert)
    # Window of 1 second — old alert is outside it
    is_dup = await db.is_duplicate_alert("0xold_alert", "ETH", window_seconds=1)
    assert is_dup is False


# ── Alert Rules ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_and_list_alert_rules(db: Database) -> None:
    """save_alert_rule and list_alert_rules round-trip."""
    rule = {
        "id": "rule_001",
        "type": "score",
        "value": 70.0,
        "window": "1h",
        "chain": "ETH",
        "webhook_url": None,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "active": True,
    }
    await db.save_alert_rule(rule)
    rules = await db.list_alert_rules()
    assert len(rules) == 1
    assert rules[0]["id"] == "rule_001"


@pytest.mark.asyncio
async def test_get_next_rule_id(db: Database) -> None:
    """get_next_rule_id increments correctly."""
    id1 = await db.get_next_rule_id()
    assert id1 == "rule_001"


# ── API Cache ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_set_and_get(db: Database) -> None:
    """cache_set and cache_get round-trip within TTL."""
    await db.cache_set("my_cache_key", '{"result": 42}', ttl_seconds=3600)
    value = await db.cache_get("my_cache_key")
    assert value == '{"result": 42}'


@pytest.mark.asyncio
async def test_cache_miss(db: Database) -> None:
    """cache_get returns None for unknown key."""
    value = await db.cache_get("nonexistent_key")
    assert value is None


@pytest.mark.asyncio
async def test_cache_expired(db: Database) -> None:
    """cache_get returns None for expired entry."""
    await db.cache_set("expired_key", '{"x": 1}', ttl_seconds=0)
    # TTL of 0 means instantly expired
    import asyncio

    await asyncio.sleep(0.01)
    value = await db.cache_get("expired_key")
    assert value is None


@pytest.mark.asyncio
async def test_cache_prune(db: Database) -> None:
    """cache_prune deletes expired entries."""
    await db.cache_set("stale_key", "data", ttl_seconds=0)
    await db.cache_set("fresh_key", "data", ttl_seconds=3600)
    import asyncio

    await asyncio.sleep(0.01)
    deleted = await db.cache_prune()
    assert deleted >= 1
    assert await db.cache_get("fresh_key") == "data"
