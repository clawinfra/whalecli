"""
Bitcoin fetcher — Mempool.space + Blockchain.info.

Primary source: Mempool.space (recent + mempool, no key required).
Fallback: Blockchain.info (historical data, no key required).

Design decisions:
- Mempool.space is preferred for anything < 24 hours (better mempool data).
- Blockchain.info is used as fallback for historical data (> 24 hours).
- No API key required for either service.
- Supports P2PKH (1...), P2SH (3...), and Bech32 (bc1...) address formats.
- BTC values stored as Decimal in BTC (not satoshis) for consistency.

Rate limits:
- Mempool.space: ~10 req/sec unauthenticated.
- Blockchain.info: ~1 req/sec; we sleep 1.1s between requests.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx

from whalecli.exceptions import ConnectionFailedError, NetworkTimeoutError
from whalecli.models import Transaction

MEMPOOL_BASE = "https://mempool.space/api"
BLOCKCHAIN_BASE = "https://blockchain.info"

SATOSHIS_PER_BTC = Decimal(100_000_000)

# BTC address patterns
_P2PKH_RE = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$")
_P2SH_RE = re.compile(r"^3[a-km-zA-HJ-NP-Z1-9]{25,34}$")
_BECH32_RE = re.compile(r"^bc1[a-z0-9]{6,87}$")


class BTCFetcher:
    """
    Async Bitcoin transaction fetcher.

    Uses Mempool.space for recent data, Blockchain.info for historical fallback.
    No API keys required.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_transactions(self, address: str, hours: int) -> list[Transaction]:
        """
        Fetch BTC transactions for `address` in the last `hours`.

        For hours <= 24: uses Mempool.space /address/{addr}/txs.
        For hours > 24: uses Blockchain.info /rawaddr/{addr} with pagination.
        Merges and deduplicates by txid.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)

        try:
            # Always try Mempool.space first for recent confirmed + unconfirmed
            mempool_txns = await self._fetch_mempool(address, cutoff)
        except (NetworkTimeoutError, ConnectionFailedError):
            mempool_txns = []

        if hours > 24:
            # Supplement with Blockchain.info for historical range
            try:
                historical_txns = await self._fetch_blockchain_info(address, cutoff)
            except (NetworkTimeoutError, ConnectionFailedError):
                historical_txns = []
        else:
            historical_txns = []

        # Merge and deduplicate by txid
        all_txns: dict[str, Transaction] = {}
        for t in mempool_txns + historical_txns:
            all_txns[t.tx_hash] = t

        return sorted(all_txns.values(), key=lambda x: x.timestamp, reverse=True)

    async def get_mempool_txns(self, address: str) -> list[Transaction]:
        """Fetch unconfirmed mempool transactions for address."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        return await self._fetch_mempool(address, cutoff, mempool_only=True)

    async def get_wallet_age(self, address: str) -> int:
        """Days since first confirmed Bitcoin transaction for this address."""
        try:
            resp = await self._client.get(
                f"{MEMPOOL_BASE}/address/{address}/txs",
                params={"limit": 1},
            )
            data = resp.json()
            if isinstance(data, list) and data:
                last_item = data[-1]
                if "status" in last_item and "block_time" in last_item["status"]:
                    first_ts = last_item["status"]["block_time"]
                    first_dt = datetime.fromtimestamp(first_ts, tz=timezone.utc)
                    return max((datetime.now(tz=timezone.utc) - first_dt).days, 0)
        except Exception:
            pass
        return 0

    async def validate_address(self, address: str) -> bool:
        """
        Validate BTC address format (no API call).

        Accepts:
        - Legacy P2PKH: starts with 1 (base58)
        - P2SH: starts with 3 (base58)
        - Bech32 SegWit: starts with bc1
        """
        return bool(
            _P2PKH_RE.match(address) or _P2SH_RE.match(address) or _BECH32_RE.match(address)
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ──────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────

    async def _fetch_mempool(
        self,
        address: str,
        cutoff: datetime,
        mempool_only: bool = False,
    ) -> list[Transaction]:
        """Fetch transactions from Mempool.space."""
        results: list[Transaction] = []

        try:
            resp = await self._client.get(f"{MEMPOOL_BASE}/address/{address}/txs")
        except httpx.TimeoutException as e:
            raise NetworkTimeoutError(f"Mempool.space timeout: {e}") from e
        except httpx.ConnectError as e:
            raise ConnectionFailedError(f"Cannot connect to Mempool.space: {e}") from e

        data = resp.json()
        if not isinstance(data, list):
            return results

        for raw in data:
            # Unconfirmed txns have no block_time in status
            status = raw.get("status", {})
            block_time = status.get("block_time")

            if mempool_only and block_time:
                continue  # Only want unconfirmed

            if block_time:
                ts = datetime.fromtimestamp(block_time, tz=timezone.utc)
                if ts < cutoff:
                    continue
                ts_str = ts.isoformat()
            else:
                ts_str = datetime.now(tz=timezone.utc).isoformat()

            t = self._parse_mempool_tx(raw, address, ts_str)
            if t:
                results.append(t)

        return results

    async def _fetch_blockchain_info(self, address: str, cutoff: datetime) -> list[Transaction]:
        """Fetch historical transactions from Blockchain.info (paginated)."""
        results: list[Transaction] = []
        offset = 0

        while True:
            await asyncio.sleep(1.1)  # Blockchain.info rate limit: ~1 req/sec
            try:
                resp = await self._client.get(
                    f"{BLOCKCHAIN_BASE}/rawaddr/{address}",
                    params={"offset": offset, "limit": 50},
                )
            except httpx.TimeoutException as e:
                raise NetworkTimeoutError(f"Blockchain.info timeout: {e}") from e
            except httpx.ConnectError as e:
                raise ConnectionFailedError(f"Cannot connect to Blockchain.info: {e}") from e

            data = resp.json()
            txns = data.get("txs", [])
            if not txns:
                break

            for raw in txns:
                ts_unix = raw.get("time", 0)
                ts = datetime.fromtimestamp(ts_unix, tz=timezone.utc)
                if ts < cutoff:
                    # Pagination is newest-first, so once we hit cutoff, stop
                    return results

                t = self._parse_blockchain_info_tx(raw, address, ts.isoformat())
                if t:
                    results.append(t)

            offset += len(txns)
            if offset >= data.get("n_tx", 0):
                break

        return results

    def _parse_mempool_tx(
        self, raw: dict[str, Any], address: str, ts_str: str
    ) -> Transaction | None:
        """Parse a Mempool.space API transaction."""
        try:
            txid = raw["txid"]
            status = raw.get("status", {})
            block_num = status.get("block_height")

            # Compute net value for this address
            # vout: outputs (received), vin: inputs (sent)
            received_sats = sum(
                v.get("value", 0)
                for v in raw.get("vout", [])
                if address in (v.get("scriptpubkey_address") or "")
            )
            sent_sats = sum(
                v.get("prevout", {}).get("value", 0)
                for v in raw.get("vin", [])
                if address in (v.get("prevout", {}).get("scriptpubkey_address") or "")
            )

            is_inflow = received_sats > sent_sats
            value_sats = abs(received_sats - sent_sats)
            value_btc = Decimal(value_sats) / SATOSHIS_PER_BTC
            fee_sats = raw.get("fee", 0)

            # Determine from/to for normalization
            if is_inflow:
                from_addr = "multiple"  # BTC txns can have multiple inputs
                to_addr = address
            else:
                from_addr = address
                to_addr = "multiple"

            return Transaction(
                tx_hash=txid,
                chain="BTC",
                block_num=block_num,
                timestamp=ts_str,
                from_addr=from_addr,
                to_addr=to_addr,
                value_native=value_btc,
                value_usd=None,
                gas_usd=None,  # Fee handled separately
                token_symbol=None,
                token_addr=None,
                fetched_at="",
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _parse_blockchain_info_tx(
        self, raw: dict[str, Any], address: str, ts_str: str
    ) -> Transaction | None:
        """Parse a Blockchain.info rawaddr transaction."""
        try:
            txid = raw["hash"]

            received_sats = sum(
                o.get("value", 0) for o in raw.get("out", []) if o.get("addr") == address
            )
            sent_sats = sum(
                i.get("prev_out", {}).get("value", 0)
                for i in raw.get("inputs", [])
                if i.get("prev_out", {}).get("addr") == address
            )

            is_inflow = received_sats > sent_sats
            value_sats = abs(received_sats - sent_sats)
            value_btc = Decimal(value_sats) / SATOSHIS_PER_BTC

            from_addr = "multiple" if is_inflow else address
            to_addr = address if is_inflow else "multiple"

            return Transaction(
                tx_hash=txid,
                chain="BTC",
                block_num=raw.get("block_height"),
                timestamp=ts_str,
                from_addr=from_addr,
                to_addr=to_addr,
                value_native=value_btc,
                value_usd=None,
                gas_usd=None,
                token_symbol=None,
                token_addr=None,
                fetched_at="",
            )
        except (KeyError, ValueError, TypeError):
            return None
