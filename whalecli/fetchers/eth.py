"""Etherscan API client for Ethereum data."""

import httpx
from typing import List
from datetime import datetime, timedelta
from whalecli.db import Transaction


BASE_URL = "https://api.etherscan.io/api"


async def fetch_transactions(address: str, hours: int, api_key: str) -> List[Transaction]:
    """Fetch recent Ethereum transactions for an address.

    Args:
        address: ETH wallet address.
        hours: Time window in hours.
        api_key: Etherscan API key.

    Returns:
        List of Transaction objects.

    Raises:
        httpx.HTTPError: If API request fails.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Return empty list
    return []


async def fetch_token_transfers(address: str, hours: int, api_key: str) -> List[Transaction]:
    """Fetch ERC-20 token transfers for an address.

    Args:
        address: ETH wallet address.
        hours: Time window in hours.
        api_key: Etherscan API key.

    Returns:
        List of Transaction objects.

    Raises:
        httpx.HTTPError: If API request fails.
    """
    # TODO: Implement in Builder phase
    return []


def calculate_usd_value(tx: dict, prices: dict) -> float:
    """Convert ETH or token amount to USD.

    Args:
        tx: Transaction data from Etherscan.
        prices: Price data dict (ETH -> USD, tokens -> USD).

    Returns:
        USD value as float.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Return 0
    return 0.0


def validate_address(address: str) -> bool:
    """Validate Ethereum address format.

    Args:
        address: Address to validate.

    Returns:
        True if valid ETH address, False otherwise.
    """
    # TODO: Implement in Builder phase
    # Basic check: starts with 0x and is 42 characters
    return address.startswith("0x") and len(address) == 42
