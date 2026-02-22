"""
Hyperliquid fetcher — Perpetual futures flows.

Fetches large position data and recent fills from the Hyperliquid API.
No API key required (public endpoints).

Hyperliquid API: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint

Design decisions:
- Uses POST /info for all data (Hyperliquid's single endpoint design).
- Address format is ETH-compatible (same 0x + 40 hex format).
- Positions translated to Transaction model with value_usd = fill size.
- Perp flows are complementary to ETH on-chain data, not a replacement.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from whalecli.exceptions import APIError, ConnectionFailedError, NetworkTimeoutError
from whalecli.models import HLPosition, Transaction

HL_API_URL = "https://api.hyperliquid.xyz/info"

ETH_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


class HyperliquidClient:
    """
    Async Hyperliquid perp API client.

    No API key required. Rate limits: undocumented, ~10 req/sec observed.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_transactions(self, address: str, hours: int) -> list[Transaction]:
        """
        Fetch Hyperliquid fills (trades) for address in the last `hours`.

        Fills are translated to Transaction model:
        - from_addr: address if selling/short, counterparty if buying/long
        - to_addr: counterparty if selling, address if buying
        - value_native: fill size in asset units (Decimal)
        - value_usd: fill size × fill price (USD notional)
        """
        cutoff = datetime.now(tz=UTC) - timedelta(hours=hours)
        fills = await self._get_fills(address)

        txns: list[Transaction] = []
        for fill in fills:
            ts_ms = fill.get("time", 0)
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
            if ts < cutoff:
                continue

            side = fill.get("side", "")  # "B" = buy, "A" = sell
            px = float(fill.get("px", 0))
            sz = Decimal(str(fill.get("sz", 0)))
            notional_usd = float(sz) * px

            is_buy = side == "B"
            from_addr = "market" if is_buy else address
            to_addr = address if is_buy else "market"

            txns.append(
                Transaction(
                    tx_hash=f"hl_{fill.get('oid', '')}_{fill.get('tid', '')}",
                    chain="HL",
                    block_num=None,
                    timestamp=ts.isoformat(),
                    from_addr=from_addr,
                    to_addr=to_addr,
                    value_native=sz,
                    value_usd=notional_usd,
                    gas_usd=float(fill.get("fee", 0)),
                    token_symbol=fill.get("coin"),
                    token_addr=None,
                    fetched_at="",
                )
            )

        return sorted(txns, key=lambda x: x.timestamp, reverse=True)

    async def get_large_positions(self, address: str) -> list[HLPosition]:
        """Fetch current open perp positions for address."""
        try:
            resp = await self._client.post(
                HL_API_URL,
                json={"type": "clearinghouseState", "user": address},
            )
        except httpx.TimeoutException as e:
            raise NetworkTimeoutError(f"Hyperliquid timeout: {e}") from e
        except httpx.ConnectError as e:
            raise ConnectionFailedError(f"Cannot connect to Hyperliquid: {e}") from e

        if resp.status_code != 200:
            raise APIError(f"Hyperliquid API error: HTTP {resp.status_code}")

        data = resp.json()
        asset_positions = data.get("assetPositions", [])

        positions: list[HLPosition] = []
        for ap in asset_positions:
            pos = ap.get("position", {})
            szi = float(pos.get("szi", 0))
            if szi == 0:
                continue  # No open position

            entry_px = float(pos.get("entryPx") or 0)
            unrealized_pnl = float(pos.get("unrealizedPnl") or 0)
            asset = pos.get("coin", "")
            size_usd = abs(szi) * entry_px

            positions.append(
                HLPosition(
                    address=address,
                    asset=asset,
                    side="long" if szi > 0 else "short",
                    size_usd=size_usd,
                    entry_price=entry_px,
                    unrealized_pnl=unrealized_pnl,
                    timestamp=datetime.now(tz=UTC).isoformat(),
                )
            )

        return positions

    async def get_wallet_age(self, address: str) -> int:
        """Days since first fill on Hyperliquid for this address."""
        fills = await self._get_fills(address)
        if not fills:
            return 0
        oldest_fill = min(fills, key=lambda f: f.get("time", float("inf")))
        ts_ms = oldest_fill.get("time", 0)
        first_dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        return max((datetime.now(tz=UTC) - first_dt).days, 0)

    async def validate_address(self, address: str) -> bool:
        """HL uses ETH-compatible 0x addresses."""
        return bool(ETH_ADDRESS_RE.match(address))

    async def close(self) -> None:
        await self._client.aclose()

    # ──────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────

    async def _get_fills(self, address: str) -> list[dict[str, Any]]:
        """Fetch all fills for address from Hyperliquid."""
        try:
            resp = await self._client.post(
                HL_API_URL,
                json={"type": "userFills", "user": address},
            )
        except httpx.TimeoutException as e:
            raise NetworkTimeoutError(f"Hyperliquid timeout: {e}") from e
        except httpx.ConnectError as e:
            raise ConnectionFailedError(f"Cannot connect to Hyperliquid: {e}") from e

        if resp.status_code != 200:
            raise APIError(f"Hyperliquid API error: HTTP {resp.status_code}")

        data = resp.json()
        return data if isinstance(data, list) else []
