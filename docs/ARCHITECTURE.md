# Architecture — whalecli

> Agent-native whale wallet tracker. ETH + BTC + Hyperliquid perp flows.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL DATA SOURCES                          │
│                                                                         │
│  Etherscan API      Mempool.space        Blockchain.info   Hyperliquid  │
│  (ETH txns,         (BTC mempool,        (BTC historical   (perp flow   │
│   token xfers)       fee estimates)       data)             data)       │
└────────┬───────────────────┬──────────────────────┬───────────┬────────┘
         │                   │                      │           │
         ▼                   ▼                      ▼           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            FETCHER LAYER                                │
│                                                                         │
│  fetchers/eth.py       fetchers/btc.py              fetchers/hl.py     │
│  ─────────────────     ──────────────────           ─────────────────  │
│  EtherscanClient       MempoolClient                HyperliquidClient  │
│  rate-limited,         multi-source                 async REST         │
│  paged responses       fallback chain               no key required    │
│  async httpx           async httpx                                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           CACHE / DB LAYER                              │
│                                                                         │
│  db.py — aiosqlite                                                      │
│  ─────────────────────────────────────────────────────────────────────  │
│  wallets table          transactions table        scores table          │
│  (tracked addresses)    (raw tx records,          (score snapshots,     │
│                          TTL-cached)               time-series)         │
│                                                                         │
│  Cache strategy:                                                        │
│  · ETH: 15-min TTL for recent blocks, 24h for old                      │
│  · BTC: 5-min TTL for mempool, 24h for confirmed                       │
│  · Scores: recomputed if source data > 5 min stale                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           SCORER ENGINE                                 │
│                                                                         │
│  scorer.py — WhaleScoringEngine                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│  Inputs: transactions, wallet_age, peer_wallets, exchange_addrs        │
│                                                                         │
│  Component 1: Net Flow Score          (0–40 pts)                       │
│  Component 2: Velocity Score          (0–25 pts)                       │
│  Component 3: Correlation Score       (0–20 pts)                       │
│  Component 4: Exchange Flow Score     (0–15 pts)                       │
│                                                                         │
│  TOTAL: 0–100, threshold ≥70 → alert                                   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                   ┌─────────────┴──────────────┐
                   ▼                            ▼
┌──────────────────────────┐     ┌──────────────────────────────────────┐
│       ALERT ENGINE       │     │          STREAM ENGINE               │
│                          │     │                                      │
│  alert.py                │     │  stream.py                           │
│  ──────────────────────  │     │  ──────────────────────────────────  │
│  ThresholdDetector       │     │  AsyncJSONLStream                    │
│  AlertFormatter          │     │  poll interval: configurable         │
│  webhook dispatch        │     │  yields WalletEvent objects          │
│  (HTTP POST to URL)      │     │  backpressure-aware                  │
└──────────┬───────────────┘     └────────────────────┬─────────────────┘
           │                                          │
           └──────────────────┬───────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          OUTPUT LAYER                                   │
│                                                                         │
│  output.py — FormatRouter                                               │
│  ─────────────────────────────────────────────────────────────────────  │
│  format=json    → JSON to stdout, deterministic key order               │
│  format=jsonl   → JSONL stream (one event per line, newline-delimited)  │
│  format=table   → Rich table to stdout (stderr-safe)                    │
│  format=csv     → CSV to stdout, header row always present              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                   ┌─────────────┴──────────────┐
                   ▼                            ▼
┌──────────────────────────┐     ┌──────────────────────────────────────┐
│   CLI ENTRY POINT        │     │       AGENT SKILL                    │
│                          │     │                                      │
│  cli.py — Click groups   │     │  skill/whalecli_skill.py             │
│  ──────────────────────  │     │  ──────────────────────────────────  │
│  wallet / scan / alert   │     │  OpenClaw skill wrapper              │
│  stream / report         │     │  trigger phrase parser               │
│  config                  │     │  subprocess call → JSON parse        │
│                          │     │  Simmer/Polymarket integration       │
└──────────────────────────┘     └──────────────────────────────────────┘
```

---

## Module Breakdown

| Module | Responsibility | Key Classes/Functions |
|---|---|---|
| `cli.py` | Click CLI entry point. All command groups registered here. | `cli`, `wallet`, `scan`, `alert`, `stream`, `report`, `config_cmd` |
| `config.py` | TOML config loading with env var overrides. | `WhalecliConfig`, `load_config()`, `save_config()` |
| `db.py` | SQLite state. Wallet registry, tx cache, score history. | `Database`, `init_db()`, `get_wallet()`, `upsert_transaction()` |
| `fetchers/eth.py` | Etherscan API client. Paged txn fetch, token transfers. | `EtherscanClient`, `get_transactions()`, `get_token_transfers()` |
| `fetchers/btc.py` | Mempool.space + Blockchain.info BTC data. | `BTCFetcher`, `get_mempool_txns()`, `get_address_history()` |
| `fetchers/hl.py` | Hyperliquid perp API. Open interest, large positions. | `HyperliquidClient`, `get_large_positions()` |
| `scorer.py` | Composite whale score (0–100). | `WhaleScoringEngine`, `score_wallet()`, `ScoreBreakdown` |
| `alert.py` | Threshold detection, alert formatting, webhook dispatch. | `AlertEngine`, `check_thresholds()`, `dispatch_webhook()` |
| `stream.py` | JSONL streaming loop with configurable poll interval. | `WhalecliStream`, `stream_events()`, `StreamEvent` |
| `output.py` | Format routing: json / jsonl / table / csv. | `FormatRouter`, `render()` |
| `skill/whalecli_skill.py` | OpenClaw skill: parses triggers, calls CLI subprocess. | `WhalecliSkill`, `handle()`, `parse_output()` |

---

## Data Flow: Full Path Example

```
User / Agent:  whalecli scan --chain ETH --hours 24 --format json
                    │
                    ▼
cli.py: scan command invoked
  → parse args: chain=ETH, hours=24, format=json
  → load config (config.py)
  → load tracked ETH wallets from db.wallets
                    │
                    ▼
For each wallet address:
  db.py: check transaction cache
    → cache miss (older than 15 min) → fetch from API
    → cache hit → use stored data
                    │
              (cache miss path)
                    ▼
fetchers/eth.py: EtherscanClient.get_transactions(address, hours=24)
  → GET https://api.etherscan.io/api?...
  → paginate until all txns in window collected
  → return List[ETHTransaction]
                    │
                    ▼
db.py: upsert_transactions(txns) → cache with TTL=15min
                    │
                    ▼
scorer.py: WhaleScoringEngine.score_wallet(address, txns, peers, config)
  → net_flow_score(txns, wallet_age)         → 0–40 pts
  → velocity_score(txns, historical_avg)    → 0–25 pts
  → correlation_score(txns, peer_wallets)   → 0–20 pts
  → exchange_flow_score(txns, exchange_db)  → 0–15 pts
  → total = sum, clamp 0–100
  → return ScoreBreakdown(total=85, ...)
                    │
                    ▼
alert.py: check_thresholds(score_breakdown, config.alert)
  → score 85 > threshold 70 → AlertEvent created
  → if webhook_url configured → dispatch_webhook(event)
                    │
                    ▼
output.py: FormatRouter.render(results, format="json")
  → JSON serialized to stdout, exit code 0
```

---

## Whale Scoring Algorithm

### Overview

The whale score is a **composite signal** (0–100) that measures how "significant" a wallet's recent activity is — combining flow magnitude, speed, coordination with peers, and smart money direction signals.

A score ≥ 70 triggers an alert by default (configurable).

### Component 1: Net Flow Score (0–40 pts)

**Measures:** Net USD value flowing in vs. out of the wallet in the time window.

**Formula:**
```
net_flow = total_inflow_usd - total_outflow_usd
magnitude = abs(net_flow)

age_weight = {
    wallet_age_days < 30:   1.3   # new wallets: higher signal
    wallet_age_days < 180:  1.1
    wallet_age_days < 730:  1.0
    wallet_age_days >= 730: 0.9   # old cold wallets: lower noise
}

raw_score = log10(max(magnitude, 1)) * age_weight
net_flow_score = clamp(raw_score * scale_factor, 0, 40)
```

**Scale factor:** Calibrated so that a $10M net flow in 24h = ~35 pts, $100M = ~40 pts.

**Rationale for log10:** Prevents $1B flows from dominating; keeps medium-scale moves relevant.

**Direction flag:** `"accumulating"` if net_flow > 0, `"distributing"` if net_flow < 0.

---

### Component 2: Velocity Score (0–25 pts)

**Measures:** How much faster than baseline the wallet is transacting right now.

**Formula:**
```
recent_volume_usd    = sum of |tx.value_usd| in the scan window
daily_avg_volume_usd = wallet's 30-day average daily volume (from db)

velocity_ratio = recent_volume_usd / max(daily_avg_volume_usd, 1)

velocity_score = clamp(log2(velocity_ratio) * 8.3, 0, 25)
```

**Edge cases:**
- Wallet with no 30-day history → `daily_avg = 0` → use fixed baseline of $50,000
- `velocity_ratio < 1.0` → score rounds to 0 (below average = no signal)
- `velocity_ratio > 100x` → capped at 25 pts

**Rationale:** A whale suddenly doing 20x its normal volume is a stronger signal than a whale doing 1x.

---

### Component 3: Correlation Score (0–20 pts)

**Measures:** Whether multiple tracked wallets are moving in the same direction simultaneously (coordinated action = stronger signal).

**Formula:**
```
peer_wallets = all tracked wallets on same chain, same time window
direction = sign(net_flow)  # +1 accumulating, -1 distributing

same_direction_count = count of peer_wallets where sign(peer.net_flow) == direction
total_active_peers = count of peers with abs(net_flow) > threshold

correlation_ratio = same_direction_count / max(total_active_peers, 1)

correlation_score = clamp(correlation_ratio * 20, 0, 20)
```

**Minimum quorum:** At least 2 peers must be active; otherwise `correlation_score = 0`.

**Rationale:** Single whale move = noisy. Multiple whales moving together = coordinated capital reallocation. This is the most "smart money" signal in the algorithm.

---

### Component 4: Exchange Flow Score (0–15 pts)

**Measures:** Whether the wallet is moving funds to/from known exchange addresses (distribution = to exchange, accumulation = from exchange).

**Exchange address database:**
- Binance hot/cold wallets (ETH, BTC)
- Coinbase custody addresses
- Kraken, OKX, Bybit known addresses
- Maintained as a versioned JSON file: `whalecli/data/exchange_addresses.json`

**Formula:**
```
exchange_inflow  = sum of tx.value_usd where tx.from in exchange_addrs
exchange_outflow = sum of tx.value_usd where tx.to in exchange_addrs

# Exchange outflow = whale receiving from exchange = accumulation
# Exchange inflow  = whale sending to exchange = distribution

signal_value = exchange_inflow + exchange_outflow   # magnitude
direction_matches_netflow = (exchange_outflow > exchange_inflow) == (net_flow > 0)

base_score = clamp(log10(max(signal_value, 1)) * 5, 0, 12)
direction_bonus = 3 if direction_matches_netflow else 0

exchange_flow_score = base_score + direction_bonus
```

**Rationale:** Exchange flows are the clearest on-chain signal: whales moving to exchange = distribution, from exchange = accumulation. Bonus when exchange signal confirms net flow direction.

---

### Final Score

```python
total = net_flow_score + velocity_score + correlation_score + exchange_flow_score
score = max(0, min(100, round(total)))
```

**Alert thresholds (defaults, all configurable):**
| Score | Meaning | Default Action |
|---|---|---|
| 0–39 | Low activity | No alert |
| 40–59 | Moderate activity | No alert |
| 60–69 | Elevated activity | No alert |
| 70–84 | High alert | Alert triggered |
| 85–94 | Very high alert | Alert + webhook |
| 95–100 | Extreme signal | Alert + webhook |

---

## SQLite Schema

Database location: `~/.whalecli/whale.db` (configurable)

```sql
-- Tracked whale wallets
CREATE TABLE wallets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    address      TEXT NOT NULL,
    chain        TEXT NOT NULL CHECK (chain IN ('ETH', 'BTC', 'HL')),
    label        TEXT,
    added_at     TEXT NOT NULL,   -- ISO8601 UTC
    first_seen   TEXT,            -- earliest tx timestamp (populated on first scan)
    tags         TEXT,            -- JSON array of tags e.g. ["exchange","binance"]
    active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(address, chain)
);

-- Transaction cache (raw fetched data, TTL-based)
CREATE TABLE transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chain        TEXT NOT NULL,
    tx_hash      TEXT NOT NULL,
    block_num    INTEGER,
    timestamp    TEXT NOT NULL,
    from_addr    TEXT NOT NULL,
    to_addr      TEXT NOT NULL,
    value_native TEXT NOT NULL,   -- native asset (ETH/BTC), stored as string to preserve precision
    value_usd    REAL,            -- USD value at tx time (nullable, populated when price data available)
    gas_usd      REAL,
    token_symbol TEXT,            -- NULL for native asset transfers
    token_addr   TEXT,
    fetched_at   TEXT NOT NULL,   -- when we fetched this (for TTL)
    UNIQUE(chain, tx_hash)
);

-- Whale score snapshots
CREATE TABLE scores (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    address      TEXT NOT NULL,
    chain        TEXT NOT NULL,
    computed_at  TEXT NOT NULL,
    window_hours INTEGER NOT NULL,
    total_score  INTEGER NOT NULL,
    net_flow     INTEGER NOT NULL,   -- score component
    velocity     INTEGER NOT NULL,
    correlation  INTEGER NOT NULL,
    exchange_flow INTEGER NOT NULL,
    net_flow_usd REAL,
    direction    TEXT CHECK (direction IN ('accumulating', 'distributing', 'neutral')),
    alert_triggered INTEGER NOT NULL DEFAULT 0
);

-- Alerts log
CREATE TABLE alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    address      TEXT NOT NULL,
    chain        TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    score        INTEGER NOT NULL,
    reason       TEXT NOT NULL,       -- JSON: which components exceeded thresholds
    webhook_sent INTEGER NOT NULL DEFAULT 0,
    webhook_status INTEGER            -- HTTP status code if webhook sent
);

-- Exchange address registry (bundled + user-extensible)
CREATE TABLE exchange_addresses (
    address      TEXT NOT NULL,
    chain        TEXT NOT NULL,
    exchange     TEXT NOT NULL,       -- "Binance", "Coinbase", etc.
    label        TEXT,                -- "Hot Wallet 1", "Cold Storage"
    source       TEXT NOT NULL,       -- "bundled" | "user"
    PRIMARY KEY (address, chain)
);

-- Indexes
CREATE INDEX idx_transactions_addr_chain ON transactions(from_addr, chain);
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX idx_scores_addr_chain ON scores(address, chain);
CREATE INDEX idx_alerts_triggered ON alerts(triggered_at);
```

---

## Caching Strategy

| Data Type | TTL | Rationale |
|---|---|---|
| ETH recent transactions (< 100 blocks) | 15 minutes | Block time ~12s; 15m = ~75 new blocks max missed |
| ETH historical transactions (> 1000 blocks) | 24 hours | Confirmed state doesn't change |
| BTC mempool transactions | 5 minutes | Mempool volatile; need near-real-time |
| BTC confirmed transactions | 24 hours | Immutable once confirmed |
| HL positions | 10 minutes | Perp positions can change rapidly |
| Whale scores | 5 minutes | Recompute if source data refreshed |
| USD price data | 10 minutes | CoinGecko or similar, not block-critical |

Cache invalidation is **TTL-based only** — no manual invalidation needed. `db.py` checks `fetched_at` against current time before deciding to re-fetch.

---

## Local vs Cloud Mode

### Local Mode (default)

```
whalecli → SQLite (local) → Etherscan/Mempool APIs directly
```

- All state in `~/.whalecli/whale.db`
- API keys in `~/.whalecli/config.toml`
- Single-user; no auth
- Suitable for personal use, EvoClaw integration

### Cloud Mode (Phase 2)

```
whalecli --cloud → FastAPI backend → managed PostgreSQL
```

- `config.toml`: `[cloud] url = "https://whalecli.example.com"` 
- JWT auth: `whalecli auth login`
- CLI becomes a thin REST client when cloud mode enabled
- Shared wallet registry across team
- Higher rate limits via pooled API keys

Feature flag: `config.cloud.enabled = true`. When enabled, every command routes through the cloud backend instead of local SQLite + direct API calls.

---

## Extension Points

### Adding a New Chain

1. Create `fetchers/newchain.py` implementing the `BaseFetcher` protocol:
   ```python
   class BaseFetcher(Protocol):
       async def get_transactions(self, address: str, hours: int) -> list[Transaction]: ...
       async def get_wallet_age(self, address: str) -> int: ...  # days
   ```

2. Register in `cli.py`: add chain to `SUPPORTED_CHAINS` list.
3. Add exchange addresses to `data/exchange_addresses.json`.
4. Add test in `tests/test_fetchers.py`.

### Adding a New Score Component

All components must implement:
```python
@dataclass
class ScoreComponent:
    name: str
    value: int           # 0–max_points
    max_points: int
    rationale: str       # human-readable explanation
```

Register in `scorer.py`'s `COMPONENTS` list. The engine automatically includes them in totals and output.

### Webhook Integrations

The webhook payload format is stable and versioned (`"schema_version": "1"`). Consumers should check `schema_version` for forward compatibility. See `docs/API.md` for the exact webhook payload schema.
