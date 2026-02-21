"""Whale scoring algorithm (0-100).

Calculates whale significance based on net flow, velocity, correlation, and exchange indicators.
"""

from dataclasses import dataclass
from typing import List
from datetime import datetime, timedelta
from whalecli.db import Wallet, Transaction


@dataclass
class ScoreResult:
    """Result of whale scoring."""
    final_score: int
    net_flow_score: int
    velocity_score: int
    correlation_score: int
    is_exchange_flow: bool
    net_flow_usd: float
    inflow_usd: float
    outflow_usd: float


KNOWN_EXCHANGES = {
    # Ethereum
    "0xdf21d1c36786e0e8e2ddc149f842953ee27fee37",  # Binance
    "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",    # Binance
    # Bitcoin
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut7tlqhqpm5s",  # Binance
    # Add more as needed
}


def calculate_score(wallet: Wallet, transactions: List[Transaction], all_wallets: List[Wallet]) -> ScoreResult:
    """Calculate whale score for a wallet.

    Args:
        wallet: Wallet to score.
        transactions: List of transactions for the wallet.
        all_wallets: All tracked wallets (for correlation analysis).

    Returns:
        ScoreResult object with detailed breakdown.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Return default score
    return ScoreResult(
        final_score=0,
        net_flow_score=0,
        velocity_score=0,
        correlation_score=0,
        is_exchange_flow=False,
        net_flow_usd=0.0,
        inflow_usd=0.0,
        outflow_usd=0.0
    )


def net_flow_score(wallet: Wallet, transactions: List[Transaction]) -> int:
    """Calculate net flow score (0-100).

    Score based on net flow amount, weighted by wallet age.

    Args:
        wallet: Wallet to score.
        transactions: List of transactions.

    Returns:
        Score from 0-100.
    """
    # TODO: Implement in Builder phase
    # Placeholder logic
    net_flow = sum(tx.amount_usd for tx in transactions if tx.direction == "in")
    net_flow -= sum(tx.amount_usd for tx in transactions if tx.direction == "out")

    wallet_age_days = (datetime.now() - wallet.added_at).days
    age_weight = min(1.0, wallet_age_days / 365)  # Max weight at 1 year

    score = min(100, int((abs(net_flow) / 1_000_000) * age_weight * 10))
    return score


def velocity_score(transactions: List[Transaction]) -> int:
    """Calculate velocity score (0-100).

    Score based on rate of change vs 30-day average.

    Args:
        transactions: List of transactions.

    Returns:
        Score from 0-100.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Need historical data for 30-day average
    return 0


def correlation_score(wallet: Wallet, all_wallets: List[Wallet]) -> int:
    """Calculate correlation score (0-100).

    Score based on multiple whales moving in the same direction.

    Args:
        wallet: Wallet to score.
        all_wallets: All tracked wallets.

    Returns:
        Score from 0-100.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Need transaction data for all wallets
    return 0


def is_exchange_flow(transaction: Transaction) -> bool:
    """Check if transaction is to/from a known exchange.

    Args:
        transaction: Transaction to check.

    Returns:
        True if counterparty is a known exchange.
    """
    # TODO: Implement in Builder phase
    # Placeholder: Need to parse counterparty from transaction
    return False
