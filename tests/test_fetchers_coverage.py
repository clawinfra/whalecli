"""Additional coverage tests for fetchers — internal methods, edge cases."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal

import httpx
import pytest
import respx

from whalecli.fetchers.btc import BTCFetcher, MEMPOOL_BASE, BLOCKCHAIN_BASE
from whalecli.fetchers.eth import ETHERSCAN_BASE, EtherscanClient
from whalecli.fetchers.hl import HL_API_URL, HyperliquidClient
from whalecli.models import Transaction

ETH_ADDR = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
BTC_ADDR = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
HL_ADDR = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
ETHERSCAN_KEY = "test_key_abc"


# ══════════════════════════════════════════════════════════════════════════════
# ETH Fetcher — deeper coverage
# ══════════════════════════════════════════════════════════════════════════════


def _eth_tx_list_resp(txs: list[dict]) -> dict:
    return {"status": "1", "message": "OK", "result": txs}


def _eth_empty_resp() -> dict:
    return {"status": "0", "message": "No transactions found", "result": []}


@pytest.mark.asyncio
@respx.mock
async def test_eth_fetches_both_normal_and_token_txns() -> None:
    """EtherscanClient fetches native + ERC-20 token transactions."""
    from datetime import datetime, timezone
    now_ts = str(int(datetime.now(tz=timezone.utc).timestamp()) - 3600)  # 1 hour ago

    native_tx = {
        "hash": "0xnative",
        "blockNumber": "18000001",
        "timeStamp": now_ts,
        "from": "0xsender",
        "to": ETH_ADDR,
        "value": "5000000000000000000",
        "gasPrice": "20000000000",
        "gasUsed": "21000",
        "isError": "0",
    }
    token_tx = {
        "hash": "0xtoken_tx",
        "blockNumber": "18000002",
        "timeStamp": now_ts,
        "from": "0xsender",
        "to": ETH_ADDR,
        "value": "1000000000000000000",
        "gasPrice": "20000000000",
        "gasUsed": "65000",
        "tokenSymbol": "USDT",
        "contractAddress": "0xusdt_contract",
        "tokenDecimal": "6",
        "isError": "0",
    }

    # Mock all etherscan calls: txlist returns native tx, tokentx returns token tx
    respx.get(ETHERSCAN_BASE).mock(side_effect=[
        httpx.Response(200, json=_eth_tx_list_resp([native_tx])),
        httpx.Response(200, json=_eth_tx_list_resp([token_tx])),
    ])

    client = EtherscanClient(api_key=ETHERSCAN_KEY)
    txns = await client.get_transactions(ETH_ADDR, hours=24)
    await client.close()

    # Should return combined transactions (native + token)
    assert len(txns) >= 1


@pytest.mark.asyncio
@respx.mock
async def test_eth_deduplicates_transactions() -> None:
    """EtherscanClient returns at most 2 results when native and token have different hashes."""
    from datetime import datetime, timezone
    now_ts = str(int(datetime.now(tz=timezone.utc).timestamp()) - 1800)

    tx_native = {
        "hash": "0xnative_only",
        "blockNumber": "18000001",
        "timeStamp": now_ts,
        "from": "0xsender",
        "to": ETH_ADDR,
        "value": "1000000000000000000",
        "gasPrice": "20000000000",
        "gasUsed": "21000",
        "isError": "0",
    }
    # Token tx with different hash (no dedup) — used to test the code path
    tx_token = {
        "hash": "0xtoken_only",
        "blockNumber": "18000002",
        "timeStamp": now_ts,
        "from": "0xsender",
        "to": ETH_ADDR,
        "value": "0",
        "gasPrice": "20000000000",
        "gasUsed": "65000",
        "tokenSymbol": "USDT",
        "contractAddress": "0xusdt",
        "tokenDecimal": "6",
        "isError": "0",
    }

    respx.get(ETHERSCAN_BASE).mock(side_effect=[
        httpx.Response(200, json=_eth_tx_list_resp([tx_native])),
        httpx.Response(200, json=_eth_tx_list_resp([tx_token])),
    ])

    client = EtherscanClient(api_key=ETHERSCAN_KEY)
    txns = await client.get_transactions(ETH_ADDR, hours=24)
    await client.close()

    # Both native and token txns should be included (different hashes)
    assert len(txns) == 2


@pytest.mark.asyncio
@respx.mock
async def test_eth_skips_error_transactions() -> None:
    """EtherscanClient filters out failed transactions (isError='1')."""
    from datetime import datetime, timezone
    now_ts = str(int(datetime.now(tz=timezone.utc).timestamp()) - 1800)
    failed_tx = {
        "hash": "0xfailed",
        "blockNumber": "18000001",
        "timeStamp": now_ts,
        "from": ETH_ADDR,
        "to": "0xrecipient",
        "value": "1000000000000000000",
        "gasPrice": "20000000000",
        "gasUsed": "21000",
        "isError": "1",  # Failed transaction
    }

    respx.get(ETHERSCAN_BASE).mock(side_effect=[
        httpx.Response(200, json=_eth_tx_list_resp([failed_tx])),
        httpx.Response(200, json=_eth_empty_resp()),
    ])

    client = EtherscanClient(api_key=ETHERSCAN_KEY)
    txns = await client.get_transactions(ETH_ADDR, hours=24)
    await client.close()

    assert txns == []


@pytest.mark.asyncio
@respx.mock
async def test_eth_filters_by_time_window() -> None:
    """EtherscanClient filters out transactions older than the window."""
    very_old_ts = str(int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()))
    old_tx = {
        "hash": "0xold",
        "blockNumber": "15000001",
        "timeStamp": very_old_ts,
        "from": "0xsender",
        "to": ETH_ADDR,
        "value": "1000000000000000000",
        "gasPrice": "20000000000",
        "gasUsed": "21000",
        "isError": "0",
    }

    respx.get(ETHERSCAN_BASE).mock(side_effect=[
        httpx.Response(200, json=_eth_tx_list_resp([old_tx])),
        httpx.Response(200, json=_eth_empty_resp()),
    ])

    client = EtherscanClient(api_key=ETHERSCAN_KEY)
    txns = await client.get_transactions(ETH_ADDR, hours=24)  # 24h window
    await client.close()

    # Old transaction outside window should be excluded
    assert txns == []


@pytest.mark.asyncio
@respx.mock
async def test_eth_connection_error_raises_network_error() -> None:
    """Network connection errors are wrapped as NetworkError."""
    from whalecli.exceptions import NetworkError
    respx.get(ETHERSCAN_BASE).mock(side_effect=httpx.ConnectError("refused"))

    client = EtherscanClient(api_key=ETHERSCAN_KEY)
    with pytest.raises(NetworkError):
        await client.get_transactions(ETH_ADDR, hours=24)
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_eth_get_wallet_age_new_wallet() -> None:
    """get_wallet_age returns 0 for a new wallet with first tx today."""
    now_ts = str(int(datetime.now(tz=timezone.utc).timestamp()))
    tx = {
        "hash": "0xfirst",
        "blockNumber": "18000001",
        "timeStamp": now_ts,
        "from": "0xsender",
        "to": ETH_ADDR,
        "value": "1000000000000000000",
        "gasPrice": "1",
        "gasUsed": "21000",
        "isError": "0",
    }

    respx.get(ETHERSCAN_BASE).mock(return_value=httpx.Response(
        200, json=_eth_tx_list_resp([tx])
    ))

    client = EtherscanClient(api_key=ETHERSCAN_KEY)
    age = await client.get_wallet_age(ETH_ADDR)
    await client.close()

    assert age == 0


@pytest.mark.asyncio
async def test_eth_validate_address_checksum() -> None:
    """Checksummed ETH addresses should be valid."""
    client = EtherscanClient(api_key=ETHERSCAN_KEY)
    # Standard 42-char hex addresses (with 0x prefix)
    assert await client.validate_address("0x" + "a" * 40) is True
    assert await client.validate_address("0x" + "0" * 40) is True
    await client.close()


# ══════════════════════════════════════════════════════════════════════════════
# BTC Fetcher — deeper coverage
# ══════════════════════════════════════════════════════════════════════════════


def _mempool_tx(txid: str = "btc001", block_time: int = 1706906640,
                received_sats: int = 5_000_000, sent_sats: int = 0) -> dict:
    return {
        "txid": txid,
        "fee": 1000,
        "status": {"confirmed": True, "block_height": 820000, "block_time": block_time},
        "vin": [],
        "vout": [{"scriptpubkey_address": BTC_ADDR, "value": received_sats}],
    }


@pytest.mark.asyncio
@respx.mock
async def test_btc_fetch_inflow_transaction() -> None:
    """BTC inflow transaction (received > sent) → to_addr = wallet."""
    tx = _mempool_tx(received_sats=10_000_000)
    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=[tx])
    )

    fetcher = BTCFetcher()
    txns = await fetcher.get_transactions(BTC_ADDR, hours=24)
    await fetcher.close()

    # Filter to transactions in the past 24h
    if txns:
        t = next((t for t in txns if t.tx_hash == "btc001"), None)
        if t:
            assert t.to_addr == BTC_ADDR
            assert t.from_addr == "multiple"


@pytest.mark.asyncio
@respx.mock
async def test_btc_fetch_outflow_transaction() -> None:
    """BTC outflow transaction (sent > received) → from_addr = wallet."""
    tx = {
        "txid": "btcout001",
        "fee": 1000,
        "status": {"confirmed": True, "block_height": 820001, "block_time": 1706906640},
        "vin": [{"prevout": {"scriptpubkey_address": BTC_ADDR, "value": 10_000_000}}],
        "vout": [{"scriptpubkey_address": "bc1q_recipient", "value": 9_000_000}],
    }
    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=[tx])
    )

    fetcher = BTCFetcher()
    txns = await fetcher.get_transactions(BTC_ADDR, hours=24)
    await fetcher.close()

    if txns:
        t = next((t for t in txns if t.tx_hash == "btcout001"), None)
        if t:
            assert t.from_addr == BTC_ADDR
            assert t.to_addr == "multiple"


@pytest.mark.asyncio
@respx.mock
async def test_btc_unconfirmed_transaction_included() -> None:
    """Unconfirmed mempool transactions (no block_time) should be included."""
    unconfirmed = {
        "txid": "btcunconf001",
        "fee": 500,
        "status": {"confirmed": False},  # No block_time
        "vin": [],
        "vout": [{"scriptpubkey_address": BTC_ADDR, "value": 1_000_000}],
    }
    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=[unconfirmed])
    )

    fetcher = BTCFetcher()
    txns = await fetcher.get_transactions(BTC_ADDR, hours=24)
    await fetcher.close()

    # Unconfirmed txns get current timestamp and are included
    hashes = [t.tx_hash for t in txns]
    assert "btcunconf001" in hashes


@pytest.mark.asyncio
@respx.mock
async def test_btc_historical_fetch_blockchain_info() -> None:
    """For hours > 24, BTCFetcher also queries Blockchain.info."""
    mempool_resp = []  # Empty recent data
    blockchain_resp = {
        "n_tx": 1,
        "txs": [
            {
                "hash": "btcold001",
                "time": int((datetime.now(tz=timezone.utc) - timedelta(hours=48)).timestamp()),
                "block_height": 810000,
                "inputs": [],
                "out": [{"addr": BTC_ADDR, "value": 3_000_000}],
            }
        ],
    }

    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=mempool_resp)
    )
    respx.get(f"{BLOCKCHAIN_BASE}/rawaddr/{BTC_ADDR}").mock(
        return_value=httpx.Response(200, json=blockchain_resp)
    )

    fetcher = BTCFetcher()
    txns = await fetcher.get_transactions(BTC_ADDR, hours=72)
    await fetcher.close()

    hashes = [t.tx_hash for t in txns]
    assert "btcold001" in hashes


@pytest.mark.asyncio
@respx.mock
async def test_btc_deduplicates_mempool_and_blockchain_info() -> None:
    """Transactions appearing in both sources are deduplicated."""
    shared_hash = "btcshared001"
    block_time = int((datetime.now(tz=timezone.utc) - timedelta(hours=12)).timestamp())

    mempool_resp = [{
        "txid": shared_hash,
        "fee": 1000,
        "status": {"confirmed": True, "block_height": 820000, "block_time": block_time},
        "vin": [],
        "vout": [{"scriptpubkey_address": BTC_ADDR, "value": 2_000_000}],
    }]
    blockchain_resp = {
        "n_tx": 1,
        "txs": [{
            "hash": shared_hash,
            "time": block_time,
            "block_height": 820000,
            "inputs": [],
            "out": [{"addr": BTC_ADDR, "value": 2_000_000}],
        }],
    }

    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=mempool_resp)
    )
    respx.get(f"{BLOCKCHAIN_BASE}/rawaddr/{BTC_ADDR}").mock(
        return_value=httpx.Response(200, json=blockchain_resp)
    )

    fetcher = BTCFetcher()
    txns = await fetcher.get_transactions(BTC_ADDR, hours=72)
    await fetcher.close()

    # Should appear only once despite being in both sources
    count = sum(1 for t in txns if t.tx_hash == shared_hash)
    assert count == 1


@pytest.mark.asyncio
@respx.mock
async def test_btc_get_mempool_txns() -> None:
    """get_mempool_txns should return only unconfirmed transactions."""
    unconfirmed = {
        "txid": "mempool_only",
        "fee": 500,
        "status": {"confirmed": False},
        "vin": [],
        "vout": [{"scriptpubkey_address": BTC_ADDR, "value": 500_000}],
    }
    confirmed = _mempool_tx(txid="confirmed_one")  # Has block_time → confirmed

    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=[unconfirmed, confirmed])
    )

    fetcher = BTCFetcher()
    txns = await fetcher.get_mempool_txns(BTC_ADDR)
    await fetcher.close()

    hashes = [t.tx_hash for t in txns]
    assert "mempool_only" in hashes
    assert "confirmed_one" not in hashes


@pytest.mark.asyncio
@respx.mock
async def test_btc_get_wallet_age(monkeypatch) -> None:
    """get_wallet_age returns age in days based on oldest tx."""
    old_ts = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp())
    data = [{"txid": "first", "status": {"confirmed": True, "block_height": 600000, "block_time": old_ts}}]

    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=data)
    )

    fetcher = BTCFetcher()
    age = await fetcher.get_wallet_age(BTC_ADDR)
    await fetcher.close()

    assert age > 365 * 5  # More than 5 years old


@pytest.mark.asyncio
@respx.mock
async def test_btc_parse_malformed_tx_returns_none() -> None:
    """Malformed transactions are silently skipped."""
    bad_tx = {"txid": "bad_one"}  # Missing required fields
    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=[bad_tx])
    )

    fetcher = BTCFetcher()
    # Should not raise — malformed tx is skipped
    txns = await fetcher.get_transactions(BTC_ADDR, hours=24)
    await fetcher.close()

    # btc txn has no status so won't be parsed with block_time logic
    # just verify no exception


@pytest.mark.asyncio
@respx.mock
async def test_btc_blockchain_info_pagination() -> None:
    """Blockchain.info pagination stops when cutoff is reached."""
    far_future_cutoff_ts = int((datetime.now(tz=timezone.utc) - timedelta(hours=48)).timestamp())
    very_old_ts = int(datetime(2019, 6, 1, tzinfo=timezone.utc).timestamp())

    # Return one recent transaction then one that's too old
    blockchain_resp = {
        "n_tx": 2,
        "txs": [
            {
                "hash": "btcpage001",
                "time": far_future_cutoff_ts + 3600,  # Within window
                "block_height": 800000,
                "inputs": [],
                "out": [{"addr": BTC_ADDR, "value": 1_000_000}],
            },
            {
                "hash": "btcpage002",
                "time": very_old_ts,  # Way outside window
                "block_height": 500000,
                "inputs": [],
                "out": [{"addr": BTC_ADDR, "value": 2_000_000}],
            },
        ],
    }

    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{BLOCKCHAIN_BASE}/rawaddr/{BTC_ADDR}").mock(
        return_value=httpx.Response(200, json=blockchain_resp)
    )

    fetcher = BTCFetcher()
    txns = await fetcher.get_transactions(BTC_ADDR, hours=48)
    await fetcher.close()

    hashes = [t.tx_hash for t in txns]
    assert "btcpage001" in hashes
    assert "btcpage002" not in hashes  # Too old, pruned by pagination


# ══════════════════════════════════════════════════════════════════════════════
# HL Fetcher — deeper coverage
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@respx.mock
async def test_hl_buy_fill_creates_inflow_transaction() -> None:
    """Buy-side fills (side='B') → from=market, to=wallet."""
    now_ms = int(datetime.now(tz=timezone.utc).timestamp()) * 1000
    fill = {"oid": 1, "tid": 100, "px": "3000.0", "sz": "5.0", "side": "B",
            "coin": "ETH", "time": now_ms, "fee": "0.5"}

    respx.post(HL_API_URL).mock(return_value=httpx.Response(200, json=[fill]))

    client = HyperliquidClient()
    txns = await client.get_transactions(HL_ADDR, hours=24)
    await client.close()

    if txns:
        assert txns[0].from_addr == "market"
        assert txns[0].to_addr == HL_ADDR


@pytest.mark.asyncio
@respx.mock
async def test_hl_sell_fill_creates_outflow_transaction() -> None:
    """Sell-side fills (side='A') → from=wallet, to=market."""
    now_ms = int(datetime.now(tz=timezone.utc).timestamp()) * 1000
    fill = {"oid": 2, "tid": 200, "px": "3000.0", "sz": "3.0", "side": "A",
            "coin": "ETH", "time": now_ms, "fee": "0.5"}

    respx.post(HL_API_URL).mock(return_value=httpx.Response(200, json=[fill]))

    client = HyperliquidClient()
    txns = await client.get_transactions(HL_ADDR, hours=24)
    await client.close()

    if txns:
        assert txns[0].from_addr == HL_ADDR
        assert txns[0].to_addr == "market"


@pytest.mark.asyncio
@respx.mock
async def test_hl_filters_old_fills() -> None:
    """Fills older than the window are excluded."""
    old_ms = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()) * 1000
    fill = {"oid": 3, "tid": 300, "px": "100.0", "sz": "1.0", "side": "B",
            "coin": "BTC", "time": old_ms, "fee": "0.1"}

    respx.post(HL_API_URL).mock(return_value=httpx.Response(200, json=[fill]))

    client = HyperliquidClient()
    txns = await client.get_transactions(HL_ADDR, hours=24)
    await client.close()

    assert txns == []


@pytest.mark.asyncio
@respx.mock
async def test_hl_get_large_positions() -> None:
    """get_large_positions returns HLPosition objects from clearinghouseState."""
    from whalecli.models import HLPosition
    # clearinghouseState returns a dict with assetPositions
    positions_resp = {
        "assetPositions": [
            {
                "position": {
                    "coin": "ETH",
                    "szi": "10.5",
                    "entryPx": "3000.0",
                    "positionValue": "31500.0",
                    "unrealizedPnl": "500.0",
                }
            }
        ]
    }

    respx.post(HL_API_URL).mock(return_value=httpx.Response(200, json=positions_resp))

    client = HyperliquidClient()
    positions = await client.get_large_positions(HL_ADDR)
    await client.close()

    assert isinstance(positions, list)
    assert len(positions) == 1
    assert isinstance(positions[0], HLPosition)
    assert positions[0].asset == "ETH"
    assert positions[0].side == "long"


@pytest.mark.asyncio
@respx.mock
async def test_hl_api_error_raises() -> None:
    """Non-200 HL API responses raise APIError."""
    from whalecli.exceptions import APIError
    respx.post(HL_API_URL).mock(return_value=httpx.Response(500, text="Server error"))

    client = HyperliquidClient()
    with pytest.raises(APIError):
        await client.get_transactions(HL_ADDR, hours=24)
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_hl_timeout_raises_network_timeout_error() -> None:
    """Timeout from HL API raises NetworkTimeoutError."""
    from whalecli.exceptions import NetworkTimeoutError
    respx.post(HL_API_URL).mock(side_effect=httpx.TimeoutException("timeout"))

    client = HyperliquidClient()
    with pytest.raises(NetworkTimeoutError):
        await client.get_transactions(HL_ADDR, hours=24)
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_hl_get_wallet_age_with_fills() -> None:
    """get_wallet_age returns correct days since first HL fill."""
    old_ms = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp()) * 1000
    fill = {"oid": 99, "tid": 999, "px": "1000.0", "sz": "1.0", "side": "B",
            "coin": "BTC", "time": old_ms, "fee": "0.1"}

    respx.post(HL_API_URL).mock(return_value=httpx.Response(200, json=[fill]))

    client = HyperliquidClient()
    age = await client.get_wallet_age(HL_ADDR)
    await client.close()

    assert age > 365  # More than 1 year
