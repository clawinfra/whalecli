"""Hyperliquid API client for perpetual futures flows."""

import httpx
from typing import List
from whalecli.db import Transaction


HYPERLIQUID_URL = "https://api.hyperliquid.xyz"


async def fetch_flows(hours: int) -> List[Transaction]:
    """Fetch large perpetual futures flows from Hyperliquid.

    Args:
        hours: Time window in hours.

    Returns:
        List of Transaction objects.

    Raises:
        httpx.HTTPError: If API request fails.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Return empty list
    return []


def detect_whale_position_change(position: dict) -> float:
    """Score a position change for whale significance.

    Args:
        position: Position data from Hyperliquid API.

    Returns:
        Score from 0-100.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Return 0
    return 0.0


async def get_current_prices() -> dict:
    """Get current mid prices from Hyperliquid.

    Returns:
        Dict of symbol -> price.

    Raises:
        httpx.HTTPError: If API request fails.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Return empty dict
    return {}
