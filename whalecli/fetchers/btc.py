"""Mempool.space + Blockchain.info client for Bitcoin data."""

import httpx
from typing import List
from whalecli.db import Transaction


MEMPOOL_BASE_URL = "https://mempool.space/api"
BLOCKCHAIN_INFO_URL = "https://blockchain.info"


async def fetch_transactions(address: str, hours: int) -> List[Transaction]:
    """Fetch recent Bitcoin transactions for an address.

    Args:
        address: BTC wallet address.
        hours: Time window in hours.

    Returns:
        List of Transaction objects.

    Raises:
        httpx.HTTPError: If API request fails.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Return empty list
    return []


def calculate_usd_value(tx: dict) -> float:
    """Convert BTC amount to USD.

    Args:
        tx: Transaction data from API.

    Returns:
        USD value as float.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Return 0
    return 0.0


def validate_address(address: str) -> bool:
    """Validate Bitcoin address format.

    Args:
        address: Address to validate.

    Returns:
        True if valid BTC address, False otherwise.
    """
    # TODO: Implement in Builder phase
    # Basic check: base58 or bech32 format
    # This is a simplified check
    return len(address) >= 26 and len(address) <= 90
