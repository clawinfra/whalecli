"""
Shared data models for whalecli.

These dataclasses are the canonical data shapes used across all modules:
fetchers produce them, scorer consumes them, output renders them.
Using dataclasses (not Pydantic) for zero-overhead in hot paths.
Pydantic used for config validation only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Wallet:
    """A tracked whale wallet."""

    address: str
    chain: str          # "ETH" | "BTC" | "HL"
    label: str
    tags: list[str]
    added_at: str       # ISO8601 UTC
    first_seen: str | None = None   # ISO8601 UTC; None until first scan
    active: bool = True

    def short_address(self) -> str:
        """Return truncated address for display: 0xd8dA...96045"""
        if len(self.address) > 12:
            return f"{self.address[:6]}...{self.address[-4:]}"
        return self.address

    def display_name(self) -> str:
        """Return label if set, otherwise short address."""
        return self.label if self.label else self.short_address()


@dataclass
class Transaction:
    """A single blockchain transaction, normalised across chains."""

    tx_hash: str
    chain: str
    from_addr: str
    to_addr: str
    timestamp: str              # ISO8601 UTC
    value_native: Decimal       # In chain's native unit: ETH, BTC, etc.
    block_num: int | None = None
    value_usd: float | None = None      # None if price data unavailable
    gas_usd: float | None = None
    token_symbol: str | None = None     # None for native asset transfers
    token_addr: str | None = None
    fetched_at: str = ""        # ISO8601 UTC; set by fetcher


@dataclass
class HLPosition:
    """An open Hyperliquid perpetual futures position."""

    address: str
    asset: str              # "ETH", "BTC", etc.
    side: str               # "long" | "short"
    size_usd: float
    entry_price: float
    unrealized_pnl: float
    timestamp: str          # ISO8601 UTC


@dataclass
class ScoreComponent:
    """Detailed breakdown for one component of the whale score."""

    name: str           # "net_flow" | "velocity" | "correlation" | "exchange_flow"
    value: int          # 0 to max_points
    max_points: int     # component ceiling
    rationale: str      # human-readable explanation of this component's score


@dataclass
class ScoreBreakdown:
    """
    Full whale score for a wallet at a point in time.

    Stored in the `scores` table; emitted in scan/stream output JSON.
    """

    address: str
    chain: str
    computed_at: str        # ISO8601 UTC
    window_hours: int

    # Composite score
    total: int              # 0–100; sum of all components, clamped

    # Per-component scores
    net_flow: int           # 0–40
    velocity: int           # 0–25
    correlation: int        # 0–20
    exchange_flow: int      # 0–15

    # Flow data
    direction: str          # "accumulating" | "distributing" | "neutral"
    net_flow_usd: float
    inflow_usd: float
    outflow_usd: float

    # Alert flag
    alert_triggered: bool = False

    # Optional detailed rationale per component
    components: list[ScoreComponent] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize for JSON output."""
        return {
            "address": self.address,
            "chain": self.chain,
            "computed_at": self.computed_at,
            "window_hours": self.window_hours,
            "score": self.total,
            "score_breakdown": {
                "net_flow": self.net_flow,
                "velocity": self.velocity,
                "correlation": self.correlation,
                "exchange_flow": self.exchange_flow,
            },
            "direction": self.direction,
            "net_flow_usd": self.net_flow_usd,
            "inflow_usd": self.inflow_usd,
            "outflow_usd": self.outflow_usd,
            "alert_triggered": self.alert_triggered,
        }


@dataclass
class AlertEvent:
    """A triggered alert event."""

    id: str                     # "alert_YYYYMMDD_HHMMSS_NNN"
    rule_id: str
    address: str
    chain: str
    label: str
    score: int
    triggered_at: str           # ISO8601 UTC
    score_breakdown: ScoreBreakdown | None = None
    webhook_sent: bool = False
    webhook_status: int | None = None

    def to_dict(self) -> dict:
        """Serialize for JSON output and webhook payload."""
        d = {
            "id": self.id,
            "rule_id": self.rule_id,
            "address": self.address,
            "chain": self.chain,
            "label": self.label,
            "score": self.score,
            "triggered_at": self.triggered_at,
            "webhook_sent": self.webhook_sent,
            "webhook_status": self.webhook_status,
        }
        if self.score_breakdown:
            d["score_breakdown"] = self.score_breakdown.to_dict()["score_breakdown"]
        return d


@dataclass
class AlertRule:
    """A configured alert rule."""

    id: str                     # "rule_NNN"
    type: str                   # "score" | "flow"
    value: float                # score threshold or USD flow threshold
    window: str                 # "15m" | "30m" | "1h" | "4h" | "24h"
    chain: str | None           # None = all chains
    webhook_url: str | None
    created_at: str             # ISO8601 UTC
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "value": self.value,
            "window": self.window,
            "chain": self.chain,
            "webhook_url": self.webhook_url,
            "created_at": self.created_at,
            "active": self.active,
        }
