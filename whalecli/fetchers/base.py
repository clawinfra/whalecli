"""Base fetcher protocol and shared data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class RawTransaction:
    """
    Normalized transaction record from any chain fetcher.

    All chain-specific data is normalized into this format before passing
    to the scorer. Fetchers must not emit any chain-specific types.
    """

    tx_hash: str
    timestamp: int  # Unix timestamp (UTC seconds)
    from_addr: str  # Sending address (lowercase)
    to_addr: str  # Receiving address (lowercase)
    value_native: float  # Amount in chain native unit (ETH, BTC, etc.)
    value_usd: float  # USD value at time of transaction
    tx_type: str  # "transfer" | "erc20_transfer" | "internal" | "perp_open" | "perp_close"
    chain: str  # "ETH" | "BTC" | "HL"
    block_number: int  # Block height (0 for unconfirmed)
    fee_usd: float  # Transaction fee in USD


@runtime_checkable
class BaseFetcher(Protocol):
    """
    Protocol that all chain fetchers must implement.

    Fetchers are responsible for:
    - Making API calls to blockchain data sources
    - Handling pagination and rate limiting
    - Normalizing data into RawTransaction format
    - Implementing cache-aside via the DB

    Fetchers are NOT responsible for:
    - Scoring or ranking (that's scorer.py)
    - Alerting (that's alert.py)
    - Output formatting (that's output.py)
    """

    async def fetch_transactions(
        self,
        address: str,
        from_ts: int,
        to_ts: int,
    ) -> list[RawTransaction]:
        """
        Fetch all transactions for address in the time range [from_ts, to_ts].

        Handles pagination internally. Returns an empty list if no transactions
        found in range (not an error).

        Args:
            address: Blockchain address to query
            from_ts: Start of time range (Unix timestamp, inclusive)
            to_ts: End of time range (Unix timestamp, inclusive)

        Returns:
            List of RawTransaction, sorted by timestamp ascending.

        Raises:
            APIKeyMissingError: If required API key is not configured
            APIKeyInvalidError: If API key is rejected by the data source
            RateLimitError: If rate limited after retries
        """
        ...

    async def get_wallet_age_days(self, address: str) -> int:
        """
        Return wallet age in days since its first on-chain transaction.

        Returns 0 if the wallet has no transaction history.
        Uses cache to avoid repeated API calls for the same address.
        """
        ...

    def validate_address(self, address: str) -> bool:
        """
        Validate that an address is well-formed for this chain.

        Does NOT make any network calls. Pure validation only.
        Returns True for valid addresses, False otherwise.
        """
        ...
