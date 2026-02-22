"""Additional coverage tests for db.py — edge cases and uncovered paths."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from whalecli.db import Database


@pytest_asyncio.fixture
async def db() -> Database:
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_get_cached_transactions_cache_miss(db: Database) -> None:
    """get_cached_transactions returns None on cache miss."""
    from_ts = "2026-02-01T00:00:00+00:00"
    to_ts = "2026-02-22T00:00:00+00:00"
    result = await db.get_cached_transactions("0xunknown", "ETH", from_ts, to_ts)
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_transactions_with_fresh_cache(db: Database) -> None:
    """get_cached_transactions returns list when cache is fresh."""
    address = "0xfresh_wallet"
    chain = "ETH"
    now = datetime.now(tz=timezone.utc)
    from_ts = (now - timedelta(hours=24)).isoformat()
    to_ts = now.isoformat()

    # Insert a fresh transaction
    txns = [
        {
            "chain": chain,
            "tx_hash": "0xtest_cached",
            "block_num": 100,
            "timestamp": now.isoformat(),
            "from_addr": "0xsender",
            "to_addr": address.lower(),
            "value_native": "1.0",
            "value_usd": 3000.0,
            "gas_usd": 5.0,
        }
    ]
    await db.upsert_transactions(txns)

    result = await db.get_cached_transactions(address, chain, from_ts, to_ts, ttl_hours=24)
    assert result is not None
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_remove_wallet_with_purge(db: Database) -> None:
    """remove_wallet with purge=True deletes transactions."""
    address = "0xpurge_me"
    await db.add_wallet(address, "ETH", "Purge Wallet")

    # Add a transaction for this wallet
    await db.upsert_transactions(
        [
            {
                "chain": "ETH",
                "tx_hash": "0xpurge_tx",
                "block_num": 100,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "from_addr": address.lower(),
                "to_addr": "0xrecipient",
                "value_native": "1.0",
            }
        ]
    )

    result = await db.remove_wallet(address, "ETH", purge=True)
    assert result["status"] == "removed"


@pytest.mark.asyncio
async def test_list_wallets_inactive(db: Database) -> None:
    """list_wallets with active_only=False returns inactive wallets too."""
    await db.add_wallet("0xinactive_wallet", "ETH", "Inactive")
    await db.remove_wallet("0xinactive_wallet", "ETH")

    active = await db.list_wallets(active_only=True)
    all_wallets = await db.list_wallets(active_only=False)

    active_addrs = [w["address"] for w in active]
    all_addrs = [w["address"] for w in all_wallets]

    assert "0xinactive_wallet" not in active_addrs
    assert "0xinactive_wallet" in all_addrs


@pytest.mark.asyncio
async def test_update_wallet_first_seen(db: Database) -> None:
    """update_wallet_first_seen persists the timestamp."""
    await db.add_wallet("0xfs_wallet", "ETH", "First Seen")
    first_seen = "2026-01-15T12:00:00+00:00"
    await db.update_wallet_first_seen("0xfs_wallet", "ETH", first_seen)

    w = await db.get_wallet("0xfs_wallet", "ETH")
    assert w["first_seen"] == first_seen


@pytest.mark.asyncio
async def test_save_alert_with_webhook_status(db: Database) -> None:
    """save_alert handles webhook_status field."""
    alert = {
        "address": "0xwebhook_test",
        "chain": "ETH",
        "label": "Hook Whale",
        "score": 85,
        "direction": "accumulating",
        "net_flow_usd": 5_000_000.0,
        "triggered_at": datetime.now(tz=timezone.utc).isoformat(),
        "rule_id": "rule_001",
        "webhook_sent": True,
        "webhook_status": 200,
    }
    saved = await db.save_alert(alert)
    assert saved["id"] is not None


@pytest.mark.asyncio
async def test_update_alert_webhook(db: Database) -> None:
    """update_alert_webhook updates webhook delivery status."""
    alert = {
        "address": "0xwebhook_update",
        "chain": "ETH",
        "label": "",
        "score": 80,
        "direction": "neutral",
        "net_flow_usd": 0.0,
        "triggered_at": datetime.now(tz=timezone.utc).isoformat(),
        "rule_id": "auto",
    }
    saved = await db.save_alert(alert)
    alert_id = saved["id"]

    await db.update_alert_webhook(alert_id, webhook_sent=True, webhook_status=200)

    alerts = await db.list_alerts()
    updated = next(a for a in alerts if a["id"] == alert_id)
    assert updated["webhook_sent"] is True
    assert updated["webhook_status"] == 200


@pytest.mark.asyncio
async def test_list_alerts_chain_filter(db: Database) -> None:
    """list_alerts with chain filter returns only matching chain."""
    now = datetime.now(tz=timezone.utc).isoformat()
    await db.save_alert(
        {
            "address": "0xeth_alert",
            "chain": "ETH",
            "label": "",
            "score": 80,
            "direction": "neutral",
            "net_flow_usd": 0.0,
            "triggered_at": now,
            "rule_id": "auto",
        }
    )
    await db.save_alert(
        {
            "address": "bc1qbtc_alert",
            "chain": "BTC",
            "label": "",
            "score": 85,
            "direction": "neutral",
            "net_flow_usd": 0.0,
            "triggered_at": now,
            "rule_id": "auto",
        }
    )

    eth_alerts = await db.list_alerts(chain="ETH")
    assert all(a["chain"] == "ETH" for a in eth_alerts)
    assert len(eth_alerts) == 1


@pytest.mark.asyncio
async def test_list_alerts_since_hours(db: Database) -> None:
    """list_alerts with since_hours filters recent alerts."""
    old_time = "2020-01-01T00:00:00+00:00"
    now = datetime.now(tz=timezone.utc).isoformat()

    await db.save_alert(
        {
            "address": "0xold_alert",
            "chain": "ETH",
            "label": "",
            "score": 75,
            "direction": "neutral",
            "net_flow_usd": 0.0,
            "triggered_at": old_time,
            "rule_id": "auto",
        }
    )
    await db.save_alert(
        {
            "address": "0xrecent_alert",
            "chain": "ETH",
            "label": "",
            "score": 80,
            "direction": "neutral",
            "net_flow_usd": 0.0,
            "triggered_at": now,
            "rule_id": "auto",
        }
    )

    recent = await db.list_alerts(since_hours=1)
    addrs = [a["address"] for a in recent]
    assert "0xrecent_alert" in addrs
    assert "0xold_alert" not in addrs


@pytest.mark.asyncio
async def test_import_wallets_with_errors(db: Database) -> None:
    """import_wallets handles rows with missing fields gracefully."""
    rows = [
        {"address": "", "chain": "ETH", "label": "Missing Address"},
        {"address": "0xgood_one", "chain": "", "label": "Missing Chain"},
        {"address": "0xvalid_one", "chain": "ETH", "label": "Valid"},
    ]
    result = await db.import_wallets(rows)
    assert result["errors"]  # Should have errors for bad rows
    assert result["imported"] >= 1  # Valid one should succeed
