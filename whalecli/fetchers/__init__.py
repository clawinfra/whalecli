"""
Fetcher layer for whalecli.

Provides a unified factory function `get_fetcher()` that returns the
appropriate chain-specific fetcher. All fetchers implement BaseFetcher.

Usage:
    from whalecli.fetchers import get_fetcher
    fetcher = get_fetcher("ETH", config)
    txns = await fetcher.get_transactions(address, hours=24)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from whalecli.config import WhalecliConfig
    from whalecli.models import Transaction

SUPPORTED_CHAINS = {"ETH", "BTC", "HL"}


@runtime_checkable
class BaseFetcher(Protocol):
    """
    Protocol that all chain fetchers must implement.

    Fetchers are responsible for:
    - Fetching raw transactions from chain APIs
    - Normalizing into the Transaction dataclass
    - Validating addresses (without API calls where possible)
    - Reporting wallet age (days since first tx)
    """

    async def get_transactions(self, address: str, hours: int) -> list[Transaction]:
        """
        Fetch transactions for address in the last `hours`.

        Args:
            address: Blockchain address (chain-specific format)
            hours: Look-back window in hours

        Returns:
            List of Transaction objects, sorted by timestamp descending.

        Raises:
            InvalidAddressError: Address format invalid for this chain
            RateLimitError: API rate limit exceeded
            NetworkError: Connection or timeout issue
            APIError: Upstream API returned unexpected error
        """
        ...

    async def get_wallet_age(self, address: str) -> int:
        """
        Return number of days since the wallet's first transaction.

        Returns 0 if wallet has no transaction history.
        """
        ...

    async def validate_address(self, address: str) -> bool:
        """
        Validate address format for this chain.

        Does NOT require an API call — pure local validation.
        Returns True if format is valid, False otherwise.
        """
        ...


def get_fetcher(chain: str, config: WhalecliConfig) -> BaseFetcher:
    """
    Factory: return the correct fetcher for the given chain.

    Args:
        chain: Chain identifier ("ETH", "BTC", "HL")
        config: WhalecliConfig with API keys

    Returns:
        Configured BaseFetcher implementation

    Raises:
        ValueError: Unknown chain identifier
    """
    chain = chain.upper()
    if chain not in SUPPORTED_CHAINS:
        raise ValueError(f"Unsupported chain: {chain!r}. Supported: {sorted(SUPPORTED_CHAINS)}")

    if chain == "ETH":
        from whalecli.fetchers.eth import EtherscanClient

        return EtherscanClient(api_key=config.api.etherscan_api_key)

    if chain == "BTC":
        from whalecli.fetchers.btc import BTCFetcher

        return BTCFetcher()

    if chain == "HL":
        from whalecli.fetchers.hl import HyperliquidClient

        return HyperliquidClient()

    raise ValueError(f"Unreachable: {chain}")  # pragma: no cover
