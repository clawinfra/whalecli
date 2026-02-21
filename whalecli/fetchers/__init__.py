"""Fetchers package for whalecli."""

from whalecli.fetchers.eth import fetch_transactions as fetch_eth_transactions
from whalecli.fetchers.btc import fetch_transactions as fetch_btc_transactions
from whalecli.fetchers.hl import fetch_flows as fetch_hl_flows

__all__ = [
    "fetch_eth_transactions",
    "fetch_btc_transactions",
    "fetch_hl_flows",
]
