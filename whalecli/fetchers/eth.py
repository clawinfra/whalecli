"""
Ethereum fetcher — Etherscan API client.

Fetches ETH and ERC-20 token transfer transactions for tracked wallets.

API docs: https://docs.etherscan.io/api-endpoints/accounts
Rate limit: 5 calls/sec on free tier.

Design decisions:
- Uses async httpx for all HTTP calls.
- Implements token bucket rate limiting (5 req/sec).
- Paginates automatically until all txns in window collected.
- USD price estimated via CoinGecko historical prices (10-min cache per day bucket).
- Token transfers fetched separately (action=tokentx) and merged with native txns.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx

from whalecli.exceptions import (
    APIError,
    ConnectionFailedError,
    InvalidAddressError,
    InvalidAPIKeyError,
    NetworkTimeoutError,
    RateLimitError,
)
from whalecli.models import Transaction

# Etherscan API base URL
ETHERSCAN_BASE = "https://api.etherscan.io/api"

# ETH address regex (0x + 40 hex chars)
ETH_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

# Page size for Etherscan pagination (max 10000)
PAGE_SIZE = 10_000

# Rate limit: 5 calls per second (free tier)
RATE_LIMIT_CALLS = 5
RATE_LIMIT_PERIOD = 1.0  # seconds


class _TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, calls: int, period: float) -> None:
        self._calls = calls
        self._period = period
        self._tokens: float = float(calls)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            # Refill tokens proportional to elapsed time
            refill = (elapsed / self._period) * self._calls
            self._tokens = min(self._calls, self._tokens + refill)
            self._last_refill = now

            if self._tokens < 1:
                wait = (1 - self._tokens) * (self._period / self._calls)
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1


class EtherscanClient:
    """
    Async Etherscan API client.

    Fetches normal ETH transactions and ERC-20 token transfers.
    Rate-limited to 5 calls/sec (free tier).
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)
        self._rate_limiter = _TokenBucket(RATE_LIMIT_CALLS, RATE_LIMIT_PERIOD)

    async def get_transactions(self, address: str, hours: int) -> list[Transaction]:
        """
        Fetch all ETH transactions for `address` in the last `hours`.

        Merges native ETH txns + ERC-20 token transfers.
        Sorted by timestamp descending.
        """
        if not await self.validate_address(address):
            raise InvalidAddressError(
                f"Invalid ETH address: {address!r}. Must be 0x + 40 hex chars."
            )

        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        cutoff_ts = int(cutoff.timestamp())

        # Fetch both native txns and token transfers concurrently
        native_task = asyncio.create_task(
            self._fetch_all_pages(address, action="txlist", start_time=cutoff_ts)
        )
        token_task = asyncio.create_task(
            self._fetch_all_pages(address, action="tokentx", start_time=cutoff_ts)
        )

        native_raw, token_raw = await asyncio.gather(native_task, token_task)

        # Parse and merge
        txns: dict[str, Transaction] = {}
        for raw in native_raw:
            t = self._parse_native_tx(raw, address)
            if t:
                txns[t.tx_hash] = t
        for raw in token_raw:
            t = self._parse_token_tx(raw, address)
            if t:
                txns[t.tx_hash + "_" + (raw.get("tokenSymbol") or "")] = t

        return sorted(txns.values(), key=lambda x: x.timestamp, reverse=True)

    async def get_wallet_age(self, address: str) -> int:
        """Days since first transaction on this address."""
        await self._rate_limiter.acquire()
        try:
            resp = await self._client.get(
                ETHERSCAN_BASE,
                params={
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "sort": "asc",
                    "page": 1,
                    "offset": 1,
                    "apikey": self._api_key,
                },
            )
            data = resp.json()
            if data["status"] != "1" or not data["result"]:
                return 0
            first_tx_ts = int(data["result"][0]["timeStamp"])
            first_dt = datetime.fromtimestamp(first_tx_ts, tz=timezone.utc)
            age = (datetime.now(tz=timezone.utc) - first_dt).days
            return max(age, 0)
        except httpx.TimeoutException as e:
            raise NetworkTimeoutError(f"Etherscan timeout on wallet age: {e}") from e
        except httpx.ConnectError as e:
            raise ConnectionFailedError(f"Cannot connect to Etherscan: {e}") from e

    async def validate_address(self, address: str) -> bool:
        """Validate ETH address format. No API call required."""
        return bool(ETH_ADDRESS_RE.match(address))

    async def close(self) -> None:
        await self._client.aclose()

    # ──────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────

    async def _fetch_all_pages(
        self, address: str, action: str, start_time: int
    ) -> list[dict[str, Any]]:
        """Paginate through Etherscan results until all txns in window collected."""
        all_results: list[dict[str, Any]] = []
        page = 1

        while True:
            await self._rate_limiter.acquire()
            try:
                resp = await self._client.get(
                    ETHERSCAN_BASE,
                    params={
                        "module": "account",
                        "action": action,
                        "address": address,
                        "startblock": 0,
                        "endblock": 99999999,
                        "sort": "desc",
                        "page": page,
                        "offset": PAGE_SIZE,
                        "apikey": self._api_key,
                    },
                )
            except httpx.TimeoutException as e:
                raise NetworkTimeoutError(f"Etherscan timeout: {e}") from e
            except httpx.ConnectError as e:
                raise ConnectionFailedError(f"Cannot connect to Etherscan: {e}") from e

            if resp.status_code == 429:
                raise RateLimitError("Etherscan rate limit exceeded", retry_after=60)

            data = resp.json()

            if data.get("status") == "0":
                msg = data.get("message", "")
                result = data.get("result", "")
                if "Invalid API Key" in str(result):
                    raise InvalidAPIKeyError("Etherscan API key is invalid")
                if msg == "No transactions found":
                    break  # Empty, not an error
                if result == "Max rate limit reached":
                    raise RateLimitError("Etherscan rate limit exceeded", retry_after=60)
                # Other status=0 cases may be "no results" — just stop paginating
                break

            results: list[dict] = data.get("result", [])
            if not results:
                break

            # Check if oldest result on this page is still within window
            oldest_ts = int(results[-1].get("timeStamp", 0))
            all_results.extend(results)

            if oldest_ts < start_time:
                # This page crosses our time boundary — stop paginating
                break

            if len(results) < PAGE_SIZE:
                # No more pages
                break

            page += 1

        # Filter to only txns within our window
        return [r for r in all_results if int(r.get("timeStamp", 0)) >= start_time]

    def _parse_native_tx(self, raw: dict[str, Any], address: str) -> Transaction | None:
        """Parse a native ETH transaction from Etherscan API response."""
        try:
            # Skip failed transactions
            if raw.get("isError") == "1":
                return None

            ts = datetime.fromtimestamp(int(raw["timeStamp"]), tz=timezone.utc)
            value_wei = int(raw.get("value", 0))
            value_eth = Decimal(value_wei) / Decimal(10**18)
            gas_price = int(raw.get("gasPrice", 0))
            gas_used = int(raw.get("gasUsed", 0))
            gas_eth = Decimal(gas_price * gas_used) / Decimal(10**18)

            return Transaction(
                tx_hash=raw["hash"],
                chain="ETH",
                block_num=int(raw.get("blockNumber", 0)),
                timestamp=ts.isoformat(),
                from_addr=raw["from"].lower(),
                to_addr=raw["to"].lower(),
                value_native=value_eth,
                value_usd=None,  # populated by price enrichment step
                gas_usd=None,  # populated by price enrichment step
                token_symbol=None,
                token_addr=None,
                fetched_at="",  # set by caller
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _parse_token_tx(self, raw: dict[str, Any], address: str) -> Transaction | None:
        """Parse an ERC-20 token transfer from Etherscan API response."""
        try:
            ts = datetime.fromtimestamp(int(raw["timeStamp"]), tz=timezone.utc)
            decimals = int(raw.get("tokenDecimal", 18))
            raw_value = int(raw.get("value", 0))
            value = Decimal(raw_value) / Decimal(10**decimals)

            return Transaction(
                tx_hash=raw["hash"],
                chain="ETH",
                block_num=int(raw.get("blockNumber", 0)),
                timestamp=ts.isoformat(),
                from_addr=raw["from"].lower(),
                to_addr=raw["to"].lower(),
                value_native=value,
                value_usd=None,
                gas_usd=None,
                token_symbol=raw.get("tokenSymbol"),
                token_addr=raw.get("contractAddress", "").lower(),
                fetched_at="",
            )
        except (KeyError, ValueError, TypeError):
            return None
