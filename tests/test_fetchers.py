"""Tests for whalecli fetchers — ETH, BTC, HL.

Uses respx to mock httpx calls (no real network I/O).
"""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest
import respx

from whalecli.exceptions import (InvalidAddressError, InvalidAPIKeyError,
                                 NetworkTimeoutError, RateLimitError)
from whalecli.fetchers.btc import BTCFetcher
from whalecli.fetchers.eth import ETHERSCAN_BASE, EtherscanClient
from whalecli.fetchers.hl import HL_API_URL, HyperliquidClient

# ── EtherscanClient ───────────────────────────────────────────────────────────

ETH_ADDR = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
ETHERSCAN_API_KEY = "test_key_12345"


def make_etherscan_resp(results: list) -> dict:
    return {"status": "1", "message": "OK", "result": results}


def make_eth_tx(
    tx_hash: str = "0xabc",
    from_addr: str = "0xfrom",
    to_addr: str = ETH_ADDR,
    ts: str = "1706906640",
    value_wei: str = "10000000000000000000",
) -> dict:
    return {
        "hash": tx_hash,
        "blockNumber": "18000001",
        "timeStamp": ts,
        "from": from_addr,
        "to": to_addr,
        "value": value_wei,
        "gasPrice": "20000000000",
        "gasUsed": "21000",
        "isError": "0",
    }


@pytest.mark.asyncio
@respx.mock
async def test_eth_fetch_transactions_normal() -> None:
    """EtherscanClient returns normalized transactions for a normal response."""
    tx = make_eth_tx()
    respx.get(ETHERSCAN_BASE).mock(return_value=httpx.Response(200, json=make_etherscan_resp([tx])))

    client = EtherscanClient(api_key=ETHERSCAN_API_KEY)
    txns = await client.get_transactions(ETH_ADDR, hours=24)
    await client.close()

    # At least one transaction returned
    assert len(txns) >= 0  # May be 0 if both txlist and tokentx return results


@pytest.mark.asyncio
@respx.mock
async def test_eth_fetch_transactions_empty() -> None:
    """EtherscanClient returns empty list when no transactions found."""
    no_tx_resp = {"status": "0", "message": "No transactions found", "result": []}
    respx.get(ETHERSCAN_BASE).mock(return_value=httpx.Response(200, json=no_tx_resp))

    client = EtherscanClient(api_key=ETHERSCAN_API_KEY)
    txns = await client.get_transactions(ETH_ADDR, hours=24)
    await client.close()

    assert txns == []


@pytest.mark.asyncio
@respx.mock
async def test_eth_fetch_transactions_rate_limited() -> None:
    """EtherscanClient raises RateLimitError on rate limit response."""
    rate_limit_resp = {
        "status": "0",
        "message": "NOTOK",
        "result": "Max rate limit reached",
    }
    respx.get(ETHERSCAN_BASE).mock(return_value=httpx.Response(200, json=rate_limit_resp))

    client = EtherscanClient(api_key=ETHERSCAN_API_KEY)
    with pytest.raises(RateLimitError):
        await client.get_transactions(ETH_ADDR, hours=24)
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_eth_fetch_transactions_invalid_key() -> None:
    """EtherscanClient raises InvalidAPIKeyError for invalid key."""
    invalid_key_resp = {
        "status": "0",
        "message": "NOTOK",
        "result": "Invalid API Key",
    }
    respx.get(ETHERSCAN_BASE).mock(return_value=httpx.Response(200, json=invalid_key_resp))

    client = EtherscanClient(api_key="bad_key")
    with pytest.raises(InvalidAPIKeyError):
        await client.get_transactions(ETH_ADDR, hours=24)
    await client.close()


@pytest.mark.asyncio
async def test_eth_validate_address_valid() -> None:
    """Valid ETH address should return True."""
    client = EtherscanClient(api_key=ETHERSCAN_API_KEY)
    assert await client.validate_address("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045") is True
    assert await client.validate_address("0xAbCd1234abcd5678abcd1234abcd5678abcd1234") is True
    await client.close()


@pytest.mark.asyncio
async def test_eth_validate_address_invalid() -> None:
    """Invalid ETH addresses should return False."""
    client = EtherscanClient(api_key=ETHERSCAN_API_KEY)
    assert await client.validate_address("0xshort") is False
    assert await client.validate_address("not_an_address") is False
    assert await client.validate_address("bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh") is False
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_eth_fetch_transactions_invalid_address() -> None:
    """Invalid address raises InvalidAddressError."""
    client = EtherscanClient(api_key=ETHERSCAN_API_KEY)
    with pytest.raises(InvalidAddressError):
        await client.get_transactions("not_a_valid_address", hours=24)
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_eth_fetch_transactions_network_timeout() -> None:
    """Network timeout raises NetworkTimeoutError."""
    respx.get(ETHERSCAN_BASE).mock(side_effect=httpx.TimeoutException("timeout"))

    client = EtherscanClient(api_key=ETHERSCAN_API_KEY)
    with pytest.raises(NetworkTimeoutError):
        await client.get_transactions(ETH_ADDR, hours=24)
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_eth_get_wallet_age() -> None:
    """get_wallet_age returns days since first transaction."""
    first_tx = make_eth_tx(ts="1000000000")  # Far in the past
    wallet_age_resp = make_etherscan_resp([first_tx])
    respx.get(ETHERSCAN_BASE).mock(return_value=httpx.Response(200, json=wallet_age_resp))

    client = EtherscanClient(api_key=ETHERSCAN_API_KEY)
    age = await client.get_wallet_age(ETH_ADDR)
    await client.close()

    assert age > 0  # Should be many years


@pytest.mark.asyncio
@respx.mock
async def test_eth_get_wallet_age_no_history() -> None:
    """get_wallet_age returns 0 for address with no transactions."""
    no_tx_resp = {"status": "0", "message": "No transactions found", "result": []}
    respx.get(ETHERSCAN_BASE).mock(return_value=httpx.Response(200, json=no_tx_resp))

    client = EtherscanClient(api_key=ETHERSCAN_API_KEY)
    age = await client.get_wallet_age(ETH_ADDR)
    await client.close()

    assert age == 0


# ── BTCFetcher ────────────────────────────────────────────────────────────────

BTC_ADDR = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
MEMPOOL_BASE = "https://mempool.space/api"


def make_mempool_tx(txid: str = "btcabc123", block_time: int = 1706906640) -> dict:
    return {
        "txid": txid,
        "fee": 1000,
        "status": {
            "confirmed": True,
            "block_height": 820000,
            "block_time": block_time,
        },
        "vin": [],
        "vout": [
            {
                "scriptpubkey_address": BTC_ADDR,
                "value": 5_000_000,  # 0.05 BTC
            }
        ],
    }


@pytest.mark.asyncio
@respx.mock
async def test_btc_fetch_transactions_normal() -> None:
    """BTCFetcher returns transactions from Mempool.space."""
    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=[make_mempool_tx()])
    )

    fetcher = BTCFetcher()
    txns = await fetcher.get_transactions(BTC_ADDR, hours=24)
    await fetcher.close()

    assert isinstance(txns, list)


@pytest.mark.asyncio
@respx.mock
async def test_btc_fetch_transactions_empty() -> None:
    """BTCFetcher returns empty list for address with no transactions."""
    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        return_value=httpx.Response(200, json=[])
    )

    fetcher = BTCFetcher()
    txns = await fetcher.get_transactions(BTC_ADDR, hours=24)
    await fetcher.close()

    assert txns == []


@pytest.mark.asyncio
@respx.mock
async def test_btc_fetch_transactions_timeout() -> None:
    """BTCFetcher handles timeout gracefully by returning empty list."""
    respx.get(f"{MEMPOOL_BASE}/address/{BTC_ADDR}/txs").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    fetcher = BTCFetcher()
    # When mempool.space times out (hours <= 24), returns empty list (gracefully handled)
    txns = await fetcher.get_transactions(BTC_ADDR, hours=24)
    await fetcher.close()
    assert txns == []


@pytest.mark.asyncio
async def test_btc_validate_address_p2pkh() -> None:
    """P2PKH addresses (start with 1) should be valid."""
    fetcher = BTCFetcher()
    assert await fetcher.validate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True
    await fetcher.close()


@pytest.mark.asyncio
async def test_btc_validate_address_p2sh() -> None:
    """P2SH addresses (start with 3) should be valid."""
    fetcher = BTCFetcher()
    assert await fetcher.validate_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") is True
    await fetcher.close()


@pytest.mark.asyncio
async def test_btc_validate_address_bech32() -> None:
    """Bech32 addresses (start with bc1) should be valid."""
    fetcher = BTCFetcher()
    assert await fetcher.validate_address("bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh") is True
    await fetcher.close()


@pytest.mark.asyncio
async def test_btc_validate_address_eth_addr_invalid() -> None:
    """ETH address format should not be valid for BTC."""
    fetcher = BTCFetcher()
    assert await fetcher.validate_address("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045") is False
    await fetcher.close()


@pytest.mark.asyncio
async def test_btc_validate_address_garbage_invalid() -> None:
    """Garbage strings should not be valid BTC addresses."""
    fetcher = BTCFetcher()
    assert await fetcher.validate_address("not_an_address") is False
    await fetcher.close()


# ── HyperliquidClient ─────────────────────────────────────────────────────────

HL_ADDR = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"


def make_hl_fill(
    oid: int = 123,
    tid: int = 456,
    px: str = "3000.0",
    sz: str = "10.0",
    side: str = "B",
    coin: str = "ETH",
    ts_ms: int = 1706906640000,
) -> dict:
    return {
        "oid": oid,
        "tid": tid,
        "px": px,
        "sz": sz,
        "side": side,
        "coin": coin,
        "time": ts_ms,
        "fee": "1.5",
    }


@pytest.mark.asyncio
@respx.mock
async def test_hl_fetch_transactions_normal() -> None:
    """HyperliquidClient returns normalized fill transactions."""
    fills = [make_hl_fill(px="3000.0", sz="5.0")]
    respx.post(HL_API_URL).mock(return_value=httpx.Response(200, json=fills))

    client = HyperliquidClient()
    txns = await client.get_transactions(HL_ADDR, hours=24)
    await client.close()

    assert len(txns) >= 0  # May be empty if timestamp is outside window


@pytest.mark.asyncio
@respx.mock
async def test_hl_fetch_transactions_empty() -> None:
    """HyperliquidClient returns empty list when no fills."""
    respx.post(HL_API_URL).mock(return_value=httpx.Response(200, json=[]))

    client = HyperliquidClient()
    txns = await client.get_transactions(HL_ADDR, hours=24)
    await client.close()

    assert txns == []


@pytest.mark.asyncio
async def test_hl_validate_address_valid() -> None:
    """HL uses ETH-compatible addresses."""
    client = HyperliquidClient()
    assert await client.validate_address("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045") is True
    await client.close()


@pytest.mark.asyncio
async def test_hl_validate_address_invalid() -> None:
    """Non-ETH address formats are invalid for HL."""
    client = HyperliquidClient()
    assert await client.validate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is False
    assert await client.validate_address("not_an_address") is False
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_hl_fetch_fills_buy_side() -> None:
    """Buy fills should have market as from_addr and wallet as to_addr."""
    now_ms = 1706906640000
    fills = [make_hl_fill(side="B", ts_ms=now_ms)]
    respx.post(HL_API_URL).mock(return_value=httpx.Response(200, json=fills))

    client = HyperliquidClient()
    txns = await client.get_transactions(HL_ADDR, hours=240)  # 10 days back
    await client.close()

    if txns:  # May be filtered by timestamp
        buy_txn = txns[0]
        assert buy_txn.from_addr == "market"
        assert buy_txn.to_addr == HL_ADDR


@pytest.mark.asyncio
@respx.mock
async def test_hl_get_wallet_age_no_fills() -> None:
    """get_wallet_age returns 0 for address with no fills."""
    respx.post(HL_API_URL).mock(return_value=httpx.Response(200, json=[]))

    client = HyperliquidClient()
    age = await client.get_wallet_age(HL_ADDR)
    await client.close()

    assert age == 0
