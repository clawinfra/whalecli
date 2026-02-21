# WhaleWatch CLI — Module Structure

This document defines the exact file layout, module responsibilities, and interface contracts for the `whalecli` codebase. A senior engineer should be able to implement each module from this spec alone.

---

## Complete File Layout

```
whalecli/                          # Root repo directory
│
├── README.md                      # Project overview + quick start
├── LICENSE                        # MIT
├── pyproject.toml                 # Package config, deps, entry points
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions: lint + test + coverage
│
├── docs/
│   ├── ARCHITECTURE.md            # System design + scoring algorithm
│   ├── API.md                     # Full CLI API reference + JSON schemas
│   ├── MODULES.md                 # This file
│   ├── ROADMAP.md                 # Phased delivery plan
│   └── SKILL.md                   # OpenClaw skill specification
│
├── whalecli/                      # Main Python package
│   ├── __init__.py                # Version, package metadata
│   ├── cli.py                     # Click CLI entry point — all commands
│   ├── config.py                  # Config loading (TOML + env vars)
│   ├── db.py                      # SQLite state management
│   ├── scorer.py                  # Whale score algorithm (0–100)
│   ├── alert.py                   # Threshold detection + alert formatting
│   ├── stream.py                  # JSONL streaming engine
│   ├── output.py                  # Format routing (json/table/csv/jsonl)
│   ├── models.py                  # Shared dataclasses / types
│   ├── exceptions.py              # Custom exception hierarchy
│   ├── data/
│   │   └── exchange_addresses.json  # Known exchange hot/cold wallet registry
│   ├── fetchers/
│   │   ├── __init__.py            # Re-exports BaseFetcher, factory function
│   │   ├── base.py                # BaseFetcher Protocol + RawTransaction dataclass
│   │   ├── eth.py                 # Etherscan API client
│   │   ├── btc.py                 # Mempool.space + Blockchain.info client
│   │   └── hl.py                  # Hyperliquid on-chain perp flows
│   └── skill/
│       ├── __init__.py
│       ├── whalecli_skill.py      # OpenClaw skill wrapper
│       └── SKILL.md               # Symlink or copy of docs/SKILL.md
│
└── tests/
    ├── conftest.py                # Shared fixtures (mock config, in-memory DB)
    ├── test_scorer.py             # Unit tests for whale scoring algorithm
    ├── test_alert.py              # Unit tests for alert engine
    ├── test_fetchers.py           # Unit tests for all fetchers (mocked HTTP)
    ├── test_config.py             # Unit tests for config loading
    ├── test_cli.py                # Integration tests for all CLI commands
    ├── test_output.py             # Unit tests for output formatting
    ├── test_db.py                 # Unit tests for SQLite operations
    └── test_stream.py             # Unit tests for JSONL streaming
```

---

## Module Specifications

---

### `whalecli/__init__.py`

**Purpose:** Package metadata. Defines `__version__`.

```python
"""whalecli — Agent-native whale wallet tracker."""
__version__ = "0.1.0"
__author__ = "ClawInfra"
__license__ = "MIT"
```

---

### `whalecli/models.py`

**Purpose:** All shared dataclasses. Single source of truth for data shapes. No business logic.

```python
from dataclasses import dataclass, field
from typing import Literal

Chain = Literal["ETH", "BTC", "HL"]
Direction = Literal["inflow", "outflow", "neutral"]
Signal = Literal["accumulation", "distribution", "neutral"]
Severity = Literal["info", "warning", "critical"]
OutputFormat = Literal["json", "table", "jsonl", "csv"]


@dataclass
class WalletSpec:
    """A tracked whale wallet."""
    id: int
    address: str
    chain: Chain
    label: str
    added_at: int           # Unix timestamp
    first_seen_block: int | None
    wallet_age_days: int
    is_active: bool


@dataclass
class RawTransaction:
    """Normalized transaction from any chain fetcher."""
    tx_hash: str
    timestamp: int          # Unix timestamp (UTC)
    from_addr: str
    to_addr: str
    value_native: float     # In chain native unit (ETH, BTC, etc.)
    value_usd: float        # USD at time of transaction
    tx_type: str            # "transfer" | "erc20_transfer" | "internal" | "perp_open" | "perp_close"
    chain: Chain
    block_number: int
    fee_usd: float


@dataclass
class SubScores:
    """Individual component scores for a whale score."""
    net_flow: int           # 0–100
    velocity: int           # 0–100
    correlation: int        # 0–100
    exchange_flow: int      # 0–100


@dataclass
class ScoredWallet:
    """A wallet with its computed whale score."""
    wallet: WalletSpec
    score: int              # 0–100
    severity: Severity | None   # None if score < 70
    direction: Direction
    signal: Signal
    net_flow_usd: float
    total_inflow_usd: float
    total_outflow_usd: float
    tx_count: int
    largest_tx_usd: float
    sub_scores: SubScores
    exchange_flow_fraction: float  # 0.0–1.0
    scan_window_hours: int
    transactions: list[RawTransaction] = field(default_factory=list)


@dataclass
class Alert:
    """A triggered whale alert."""
    id: int | None          # None before persistence
    wallet: WalletSpec
    triggered_at: int       # Unix timestamp
    score: int
    severity: Severity
    direction: Direction
    signal: Signal
    net_flow_usd: float
    tx_count: int
    largest_tx_usd: float
    window_hours: int
    sub_scores: SubScores


@dataclass
class ScanResult:
    """Full result of a scan command."""
    chain: str
    hours: int
    wallets_scanned: int
    threshold: int
    alerts: list[Alert]
    timestamp: int          # Unix timestamp of scan start


@dataclass
class StreamEvent:
    """A single event emitted by the stream command."""
    event_type: str         # "alert" | "heartbeat" | "error" | "scan_complete"
    stream_sequence: int
    timestamp: int
    payload: dict           # Event-specific data


@dataclass
class Config:
    """Fully loaded and validated configuration."""
    etherscan_api_key: str
    default_hours: int
    default_threshold: int
    default_chain: str
    alert_threshold: int
    usd_threshold: float
    alert_window: str
    ttl_etherscan: int
    ttl_mempool: int
    ttl_hyperliquid: int
    ttl_price: int
    cache_db_path: str
    default_format: OutputFormat
    log_level: str
    mempool_url: str
    blockchain_info_url: str
    hl_ws_url: str
    hl_rest_url: str
    hl_min_position_usd: float
    weight_net_flow: float
    weight_velocity: float
    weight_correlation: float
    weight_exchange_flow: float
    dormancy_threshold_days: int
    db_path: str
    flow_history_days: int
    cloud_enabled: bool
    cloud_server_url: str
    cloud_api_key: str
```

---

### `whalecli/exceptions.py`

**Purpose:** Custom exception hierarchy. All `whalecli` errors inherit from `WhaleCLIError`.

```python
class WhaleCLIError(Exception):
    """Base exception for all whalecli errors."""
    code: str = "UNKNOWN_ERROR"

class ConfigNotFoundError(WhaleCLIError):
    code = "CONFIG_NOT_FOUND"

class ConfigInvalidError(WhaleCLIError):
    code = "CONFIG_INVALID_SCHEMA"

class APIKeyMissingError(WhaleCLIError):
    code = "ETHERSCAN_API_KEY_MISSING"

class APIKeyInvalidError(WhaleCLIError):
    code = "ETHERSCAN_INVALID_KEY"

class RateLimitError(WhaleCLIError):
    code = "ETHERSCAN_RATE_LIMITED"

class WalletNotFoundError(WhaleCLIError):
    code = "WALLET_NOT_FOUND"

class WalletInvalidAddressError(WhaleCLIError):
    code = "WALLET_INVALID_ADDRESS"

class WalletDuplicateError(WhaleCLIError):
    code = "WALLET_DUPLICATE"

class NoWalletsTrackedError(WhaleCLIError):
    code = "NO_WALLETS_TRACKED"

class ScoringWeightError(WhaleCLIError):
    code = "SCORING_WEIGHT_ERROR"

class DatabaseError(WhaleCLIError):
    code = "DB_MIGRATION_FAILED"
```

---

### `whalecli/config.py`

**Purpose:** Load, merge, and validate configuration. Return a `Config` object.

**Public interface:**

```python
def load_config(config_path: str | None = None) -> Config:
    """
    Load config from TOML file, then apply environment variable overrides.
    
    Args:
        config_path: Override path. Defaults to ~/.whalecli/config.toml.
    
    Returns:
        Fully validated Config object.
    
    Raises:
        ConfigNotFoundError: If config file doesn't exist.
        ConfigInvalidError: If config has unknown keys or invalid values.
        ScoringWeightError: If scoring weights don't sum to 1.0.
    """

def write_default_config(config_path: str, force: bool = False) -> None:
    """
    Write a fully-commented default config.toml.
    Does nothing if file exists and force=False.
    """

def set_config_value(key: str, value: str, config_path: str | None = None) -> None:
    """
    Set a single config value by dot-notation key.
    e.g. key="api_keys.etherscan_api_key", value="abc123"
    
    Raises:
        ConfigInvalidError: If key is unknown.
    """

ENV_VAR_MAP: dict[str, str] = {
    "WHALECLI_ETHERSCAN_API_KEY": "api_keys.etherscan_api_key",
    "WHALECLI_DEFAULT_THRESHOLD": "scanning.default_threshold",
    # ... full mapping ...
}
```

**Implementation notes:**
- Use `tomllib` (stdlib Python 3.11+) for reading, `toml` for writing
- Env vars are applied AFTER file loading (env takes priority)
- Unknown TOML keys raise `ConfigInvalidError` (strict mode, prevents typos)
- `~` in paths is always expanded with `os.path.expanduser()`

---

### `whalecli/db.py`

**Purpose:** All SQLite operations. Uses `aiosqlite` for async access.

**Public interface:**

```python
class WhaleCLIDB:
    """
    Database manager. Handles both app.db (state) and cache.db (API cache).
    Performs schema migration on first connect.
    """
    
    def __init__(self, db_path: str, cache_db_path: str) -> None: ...
    
    async def connect(self) -> None:
        """Open DB connections and run migrations if needed."""
    
    async def close(self) -> None:
        """Close all connections."""
    
    # === Wallet management ===
    
    async def add_wallet(self, address: str, chain: str, label: str) -> WalletSpec:
        """
        Add wallet to tracking.
        Raises: WalletDuplicateError, WalletInvalidAddressError
        """
    
    async def list_wallets(self, chain: str | None = None) -> list[WalletSpec]:
        """Return all active tracked wallets, optionally filtered by chain."""
    
    async def remove_wallet(self, address: str) -> None:
        """
        Mark wallet as inactive (soft delete).
        Raises: WalletNotFoundError
        """
    
    async def get_wallet(self, address: str) -> WalletSpec:
        """Raises: WalletNotFoundError"""
    
    # === Flow history ===
    
    async def record_flow(
        self, wallet_id: int, day_bucket: int,
        inflow_usd: float, outflow_usd: float, tx_count: int
    ) -> None:
        """Upsert flow record for a wallet + day."""
    
    async def get_30d_avg_flow(self, wallet_id: int) -> float:
        """Return average daily flow (inflow + outflow) over last 30 days."""
    
    # === Alerts ===
    
    async def save_alert(self, alert: Alert) -> Alert:
        """Persist alert. Returns alert with id set."""
    
    async def list_alerts(
        self,
        limit: int = 20,
        since: int | None = None,
        chain: str | None = None,
        severity: str | None = None,
    ) -> list[Alert]:
        """Query recent alerts with optional filters."""
    
    async def is_alert_duplicate(
        self, wallet_id: int, window_hours: int, chain: str
    ) -> bool:
        """
        Check if this wallet already alerted within the current window bucket.
        Window bucket = floor(unix_ts / window_seconds)
        """
    
    # === API Cache ===
    
    async def cache_get(self, cache_key: str) -> str | None:
        """Return cached response if fresh, None if miss or expired."""
    
    async def cache_set(self, cache_key: str, response: str, ttl_seconds: int) -> None:
        """Store API response in cache with TTL."""
    
    async def cache_prune(self) -> int:
        """Delete expired cache entries. Returns number deleted."""
```

**Implementation notes:**
- `aiosqlite` used throughout — all methods are `async`
- `connect()` runs schema migrations: checks `db_meta.schema_version`, applies any new migrations in order
- `cache_get()` checks `fetched_at + ttl_seconds > time.time()`
- `cache_key` = `hashlib.sha256((url + sorted_params).encode()).hexdigest()`
- DB is used as context manager in CLI commands: `async with WhaleCLIDB(...) as db:`

---

### `whalecli/fetchers/base.py`

**Purpose:** Protocol definition for all fetchers. Enforces consistent interface.

```python
from typing import Protocol, runtime_checkable
from whalecli.models import RawTransaction

@runtime_checkable
class BaseFetcher(Protocol):
    """
    Protocol that all chain fetchers must implement.
    Fetchers are responsible for retrieving and normalizing transaction data.
    They do NOT score, alert, or format — that's other modules' job.
    """
    
    async def fetch_transactions(
        self,
        address: str,
        from_ts: int,    # Unix timestamp
        to_ts: int,      # Unix timestamp
    ) -> list[RawTransaction]:
        """
        Fetch all transactions for address in the time range.
        Handles pagination internally.
        Returns normalized RawTransaction list.
        """
        ...
    
    async def get_wallet_age_days(self, address: str) -> int:
        """
        Return age of wallet in days (from first on-chain transaction).
        Returns 0 if wallet has no history.
        """
        ...
    
    def validate_address(self, address: str) -> bool:
        """
        Return True if address is valid for this chain.
        Does NOT make any network calls.
        """
        ...
```

---

### `whalecli/fetchers/eth.py`

**Purpose:** Etherscan API client for Ethereum.

**Class:** `EthFetcher(BaseFetcher)`

**Implementation requirements:**
- Use `httpx.AsyncClient` for all HTTP calls
- Three Etherscan endpoints: `txlist`, `tokentx`, `txlistinternal`
- Merge all transaction types into a unified `RawTransaction` list
- De-duplicate by `tx_hash` (a tx can appear in multiple endpoints)
- Paginate automatically: if response returns 10,000 items (max per page), fetch next page
- ETH→USD conversion: call CoinGecko price API (cached 5 min), multiply `value_eth` by price
- `validate_address()`: check 0x prefix + 40 hex chars + checksum (EIP-55)
- `get_wallet_age_days()`: call `txlist?sort=asc&page=1&offset=1`, get timestamp of first tx

**Rate limiting:**
- Free Etherscan: 5 req/sec max
- Use internal semaphore: `asyncio.Semaphore(3)` (leave headroom)
- On 429 response: wait 1 second and retry once

**Key method signature:**
```python
async def fetch_transactions(
    self,
    address: str,
    from_ts: int,
    to_ts: int,
    *,
    include_token_transfers: bool = True,
    include_internal: bool = True,
) -> list[RawTransaction]:
    """
    Fetch ETH transactions (+ optional ERC-20 + internal).
    
    Raises:
        APIKeyMissingError: If etherscan_api_key is empty string
        APIKeyInvalidError: If Etherscan returns NOTOK + invalid key message
        RateLimitError: If rate limited after retry
    """
```

---

### `whalecli/fetchers/btc.py`

**Purpose:** Bitcoin transaction fetcher. Primary: Mempool.space. Fallback: Blockchain.info.

**Class:** `BtcFetcher(BaseFetcher)`

**Implementation requirements:**
- Primary: `GET https://mempool.space/api/address/{address}/txs` (paginated via `after_txid`)
- Filter by timestamp: Mempool.space returns all txs, filter by `block_time` in range
- Fallback to Blockchain.info if Mempool.space returns 5xx or times out
- BTC→USD: CoinGecko price (same cache as ETH, different coin_id: `bitcoin`)
- `validate_address()`: P2PKH (starts with 1), P2SH (starts with 3), bech32 (starts with bc1)
- Use `bech32` library for bech32 validation

**Mempool.space pagination:**
```python
# Mempool.space returns 25 txs per call
# Next page: GET /address/{addr}/txs?after_txid={last_txid}
# Stop when response is empty list
```

---

### `whalecli/fetchers/hl.py`

**Purpose:** Hyperliquid on-chain perpetual futures flow tracker.

**Class:** `HyperliquidFetcher(BaseFetcher)`

**Implementation requirements:**
- Use REST API for historical: `POST https://api.hyperliquid.xyz/info` with `type: "userFills"`
- Response: list of fills with `px` (price), `sz` (size), `side` (B/S), `time`, `coin`
- Minimum position filter: skip fills where `abs(px * sz) < config.hl_min_position_usd`
- Map fills to `RawTransaction`:
  - `tx_type = "perp_open"` if first fill for this OID in window
  - `tx_type = "perp_close"` if closing a position
  - `from_addr` = whale wallet (the Hyperliquid L1 address)
  - `to_addr` = "HYPERLIQUID_CLEARINGHOUSE" (constant)
  - `value_usd` = `px * sz` (fill notional)
- `validate_address()`: same as Ethereum (HL uses ETH-compatible addresses)
- No WebSocket in Phase 1 — REST polling only (WebSocket added in Phase 2)

---

### `whalecli/scorer.py`

**Purpose:** Compute whale score (0–100) for a wallet given its transactions.

**Public interface:**

```python
def score_wallet(
    wallet: WalletSpec,
    transactions: list[RawTransaction],
    avg_30d_daily_flow: float,
    exchange_addresses: set[str],
    all_wallet_directions: dict[str, Direction],  # {address: direction} for correlation
    config: Config,
) -> ScoredWallet:
    """
    Compute full whale score for a wallet.
    
    Args:
        wallet: The wallet being scored
        transactions: All transactions in the scan window
        avg_30d_daily_flow: Average daily USD flow for velocity baseline
        exchange_addresses: Set of known exchange addresses for exchange flow score
        all_wallet_directions: Other wallets' directions (for correlation score)
        config: Loaded configuration (weights, thresholds)
    
    Returns:
        ScoredWallet with full score breakdown
    """


def compute_net_flow_score(
    transactions: list[RawTransaction],
    wallet_age_days: int,
    dormancy_threshold_days: int,
) -> tuple[int, Direction, Signal, float, float, float]:
    """
    Compute the net flow sub-score.
    
    Returns:
        (score, direction, signal, net_flow_usd, total_inflow, total_outflow)
    """


def compute_velocity_score(
    transactions: list[RawTransaction],
    avg_30d_daily_flow: float,
    scan_hours: int,
) -> int:
    """
    Compute velocity sub-score based on unusual activity level.
    Returns score 0–100.
    """


def compute_correlation_score(
    wallet_direction: Direction,
    all_wallet_directions: dict[str, Direction],
) -> int:
    """
    Compute correlation sub-score.
    Measures what fraction of other wallets share this direction.
    Returns score 0–100.
    """


def compute_exchange_flow_score(
    transactions: list[RawTransaction],
    exchange_addresses: set[str],
) -> tuple[int, float, Signal | None]:
    """
    Compute exchange flow sub-score.
    
    Returns:
        (score, exchange_flow_fraction, direction_override_or_none)
    """


def load_exchange_addresses(chain: Chain) -> set[str]:
    """
    Load exchange addresses for the given chain from the bundled JSON registry.
    Returns lowercase address strings.
    """
```

**Implementation notes:**
- All functions are **pure** (no side effects, no I/O) — makes testing trivial
- `score_wallet()` calls the four sub-score functions in order
- Correlation score is computed AFTER all wallets have their direction determined
- The `all_wallet_directions` dict is built by `cli.py` after the first scoring pass
- Exchange addresses JSON: `whalecli/data/exchange_addresses.json`

---

### `whalecli/alert.py`

**Purpose:** Alert detection, deduplication, and formatting.

**Public interface:**

```python
async def process_alerts(
    scored_wallets: list[ScoredWallet],
    db: WhaleCLIDB,
    config: Config,
    scan_window_hours: int,
) -> list[Alert]:
    """
    Filter scored wallets into alerts based on configured thresholds.
    Deduplicates against recent alerts in DB.
    Persists new alerts to DB.
    
    Args:
        scored_wallets: All scored wallets from the scan
        db: Database connection
        config: Config (thresholds)
        scan_window_hours: Current scan window (for dedup key)
    
    Returns:
        List of new (not duplicate) alerts that met threshold.
    """


def score_to_severity(score: int) -> Severity | None:
    """
    70–79 → "info"
    80–89 → "warning"
    90+   → "critical"
    < 70  → None
    """


def format_alert_for_display(alert: Alert) -> str:
    """Format a single alert as a human-readable string for table mode."""


def compute_scan_summary(alerts: list[Alert], wallets_scanned: int) -> dict:
    """
    Compute the 'summary' field for scan output.
    Determines dominant_signal and fear_greed_implication.
    """
```

**Alert deduplication logic:**
```python
# Dedup key: same wallet + same chain + same window bucket
# Window bucket = floor(current_unix_ts / dedup_window_seconds)
# Default dedup_window = 1h = 3600 seconds

async def is_duplicate(self, wallet_id: int, window_hours: int) -> bool:
    # Query alerts table for same wallet_id in current bucket
    current_bucket = int(time.time()) // 3600
    ...
```

---

### `whalecli/stream.py`

**Purpose:** Implements the `whalecli stream` polling loop. Emits JSONL to stdout.

**Public interface:**

```python
async def run_stream(
    chains: list[Chain],
    interval_seconds: int,
    threshold: int,
    heartbeat_every: int,
    config: Config,
    db: WhaleCLIDB,
) -> None:
    """
    Main stream loop. Runs until cancelled (KeyboardInterrupt → clean exit 130).
    
    On each poll:
    1. Fetch transactions for all wallets on specified chains
    2. Score all wallets
    3. For any wallet scoring >= threshold: emit alert JSONL line
    4. Every heartbeat_every polls: emit heartbeat JSONL line
    5. Emit scan_complete JSONL line after each full poll cycle
    
    Handles KeyboardInterrupt gracefully: flushes stdout, exits with code 130.
    """


def emit_event(event: StreamEvent) -> None:
    """
    Serialize event to JSON and write to stdout with newline.
    Forces flush after each write (critical for pipe consumers).
    """


def make_alert_event(alert: Alert, sequence: int) -> StreamEvent:
    """Build a StreamEvent of type 'alert' from an Alert object."""


def make_heartbeat_event(
    wallets_monitored: int,
    last_alert_at: int | None,
    interval_seconds: int,
    sequence: int,
) -> StreamEvent:
    """Build a StreamEvent of type 'heartbeat'."""
```

**Implementation notes:**
- `sys.stdout.write(json.dumps(event_dict) + "\n")` + `sys.stdout.flush()` — never use `print()` buffering
- Each poll cycle: `await asyncio.gather(*[fetch_and_score(wallet) for wallet in wallets])` — parallel
- `KeyboardInterrupt` caught at top level, calls `sys.exit(130)`
- Sequence counter is monotonically increasing per process run (not persisted)

---

### `whalecli/output.py`

**Purpose:** Serialize result objects to the requested output format.

**Public interface:**

```python
def format_output(result: ScanResult | list | dict, format: OutputFormat) -> str:
    """
    Serialize result to requested format string.
    Caller writes this to stdout.
    """


def format_json(result: Any) -> str:
    """Pretty-print JSON (2-space indent)."""


def format_table(result: ScanResult) -> str:
    """
    Rich-formatted table. Uses rich.table.Table.
    Green = accumulation/inflow. Red = distribution/outflow.
    """


def format_csv(result: Any) -> str:
    """CSV string with header row. Uses csv.writer."""


def result_to_dict(result: ScanResult) -> dict:
    """
    Convert a ScanResult (or any result object) to dict for JSON serialization.
    Handles: dataclasses, datetime, special types.
    """


def mask_api_key(key: str) -> str:
    """
    Mask API key for display: show first 4 chars + '****'.
    'abcdefg123' → 'abcd****'
    '''  → '****'
    """
```

---

### `whalecli/cli.py`

**Purpose:** All Click commands. Thin orchestration layer — delegates to other modules.

**Structure:**

```python
import click
import asyncio

@click.group()
@click.version_option()
@click.option("--config", envvar="WHALECLI_CONFIG", default=None)
@click.option("--format", "output_format", default="json", 
              type=click.Choice(["json", "table", "jsonl", "csv"]))
@click.option("-v", "--verbose", is_flag=True)
@click.option("-q", "--quiet", is_flag=True)
@click.pass_context
def cli(ctx, config, output_format, verbose, quiet):
    """WhaleWatch CLI — Agent-native whale wallet tracker."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)
    ctx.obj["format"] = output_format
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


@cli.group()
def wallet(): """Manage tracked whale wallets."""


@wallet.command("add")
@click.argument("address")
@click.option("--chain", required=True, type=click.Choice(["ETH", "BTC"]))
@click.option("--label", default="")
@click.pass_context
def wallet_add(ctx, address, chain, label):
    """Add a wallet to the tracking fleet."""
    # asyncio.run(db.add_wallet(...))
    # Handle WhaleCLIError → write JSON to stderr, sys.exit(2)


@wallet.command("list")
...

@wallet.command("remove")
...

@wallet.command("import")
...

@cli.command("scan")
@click.option("--chain", default="ALL", type=click.Choice(["ETH", "BTC", "ALL"]))
@click.option("--wallet", "wallet_addr", default=None)
@click.option("--hours", default=24, type=click.IntRange(1, 720))
@click.option("--threshold", default=70, type=click.IntRange(0, 100))
@click.option("--all", "include_all", is_flag=True)
@click.option("--no-cache", is_flag=True)
@click.pass_context
def scan(ctx, chain, wallet_addr, hours, threshold, include_all, no_cache):
    """Scan tracked wallets for whale activity."""
    # asyncio.run(_do_scan(...))
    # Exit 0 if alerts, 1 if no alerts, 2 if error


@cli.group()
def alert(): """Manage and view whale alerts."""

@alert.command("list")
...

@cli.command("stream")
...

@cli.command("report")
...

@cli.group()
def config(): """Manage whalecli configuration."""

@config.command("init")
...

@config.command("set")
...

@config.command("show")
...


def _handle_error(error: WhaleCLIError, command: str) -> None:
    """
    Write error JSON to stderr and sys.exit(2).
    Called from all command error handlers.
    """
    import sys, json
    err = {
        "error": True,
        "code": error.code,
        "message": str(error),
        "command": command,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    sys.stderr.write(json.dumps(err) + "\n")
    sys.exit(2)
```

**Key design rules for cli.py:**
- All async work uses `asyncio.run()` at the click command boundary
- All `WhaleCLIError` exceptions caught and routed to `_handle_error()`
- No business logic in cli.py — only argument parsing and orchestration
- Exit codes set explicitly with `sys.exit()`, never inferred

---

### `whalecli/skill/whalecli_skill.py`

**Purpose:** OpenClaw skill wrapper. Provides a Pythonic async API over the CLI.

```python
class WhaleCliSkill:
    """
    OpenClaw skill wrapper for whalecli CLI.
    
    Usage:
        skill = WhaleCliSkill()
        result = await skill.scan(chain="ETH", hours=4)
        
        async for event in skill.stream(chain="ETH", interval=60):
            print(event)
    """
    
    def __init__(self, whalecli_path: str = "whalecli"):
        self.whalecli_path = whalecli_path
    
    async def scan(
        self,
        chain: str = "ALL",
        hours: int = 24,
        threshold: int = 70,
        wallet: str | None = None,
    ) -> dict:
        """Run whalecli scan. Returns parsed JSON dict. Returns {} if no alerts."""
    
    async def report(
        self,
        summary: bool = True,
        days: int = 7,
        wallet: str | None = None,
    ) -> dict:
        """Run whalecli report. Returns parsed JSON dict."""
    
    async def alert_list(self, limit: int = 10) -> dict:
        """Run whalecli alert list. Returns parsed JSON dict."""
    
    async def stream(
        self,
        chain: str = "ALL",
        interval: int = 60,
        threshold: int = 70,
    ):
        """
        Async generator. Yields StreamEvent dicts as they arrive.
        Usage: async for event in skill.stream(): ...
        """
    
    async def add_wallet(self, address: str, chain: str, label: str = "") -> dict:
        """Add a wallet. Returns success dict or raises WhaleCLIError."""
    
    async def _run(self, *args: str) -> tuple[int, str, str]:
        """
        Internal: run whalecli subprocess.
        Returns (returncode, stdout, stderr).
        """
```

---

## Test Module Specifications

### `tests/conftest.py`

**Shared fixtures:**

```python
@pytest.fixture
def sample_config() -> Config:
    """Minimal valid Config object for tests."""

@pytest.fixture
async def in_memory_db() -> WhaleCLIDB:
    """In-memory SQLite DB (db_path=':memory:') with schema applied."""

@pytest.fixture
def sample_transactions() -> list[RawTransaction]:
    """10 sample RawTransaction objects with known values."""

@pytest.fixture
def mock_etherscan_response() -> dict:
    """Realistic mock Etherscan API response."""

@pytest.fixture
def sample_whale_wallet() -> WalletSpec:
    """A WalletSpec with realistic data for scoring tests."""
```

### `tests/test_scorer.py`

Tests must cover:
- [ ] `score_wallet()` returns score in 0–100 range
- [ ] Net flow score: $100K flow → score in expected range
- [ ] Net flow score: dormant wallet (age > 730 days) gets age boost
- [ ] Velocity score: 10x above 30d average → score > 80
- [ ] Velocity score: dormant wallet suddenly active → score 90–100
- [ ] Correlation score: all 5 wallets moving same direction → score 100
- [ ] Correlation score: 0 correlation → score 0
- [ ] Exchange flow score: 80% of flow through exchanges → score > 70
- [ ] Final score: weighted sum is correct
- [ ] Direction: net_flow_usd < 0 → `direction = "outflow"`, `signal = "distribution"`
- [ ] Score threshold: score >= 90 → `severity = "critical"`
- [ ] `load_exchange_addresses()` returns a non-empty set for ETH

### `tests/test_alert.py`

Tests must cover:
- [ ] `process_alerts()`: scored wallet above threshold → alert returned
- [ ] `process_alerts()`: scored wallet below threshold → no alert
- [ ] `process_alerts()`: duplicate within window → not re-alerted
- [ ] `process_alerts()`: duplicate in different window → alert again
- [ ] `score_to_severity()`: correct severity at 70, 80, 90 boundaries
- [ ] `compute_scan_summary()`: all distribution → `dominant_signal = "distribution"`
- [ ] `compute_scan_summary()`: mixed signals → `dominant_signal = "mixed"`

### `tests/test_fetchers.py`

Uses `respx` to mock `httpx` calls.

Tests must cover:
- [ ] `EthFetcher.fetch_transactions()`: normal response → correct RawTransaction list
- [ ] `EthFetcher.fetch_transactions()`: paginates on 10,000 item response
- [ ] `EthFetcher.fetch_transactions()`: raises `APIKeyMissingError` on empty key
- [ ] `EthFetcher.fetch_transactions()`: raises `RateLimitError` on 429
- [ ] `EthFetcher.validate_address()`: valid ETH address → True
- [ ] `EthFetcher.validate_address()`: BTC address → False
- [ ] `BtcFetcher.fetch_transactions()`: normal response → correct list
- [ ] `BtcFetcher.fetch_transactions()`: paginates via `after_txid`
- [ ] `BtcFetcher.fetch_transactions()`: falls back to blockchain.info on 5xx
- [ ] `BtcFetcher.validate_address()`: P2PKH, P2SH, bech32 all → True
- [ ] `HyperliquidFetcher.fetch_transactions()`: filters out fills below min size

### `tests/test_config.py`

Tests must cover:
- [ ] `load_config()`: valid TOML file → correct Config object
- [ ] `load_config()`: missing file → `ConfigNotFoundError`
- [ ] `load_config()`: unknown key in TOML → `ConfigInvalidError`
- [ ] `load_config()`: weights don't sum to 1.0 → `ScoringWeightError`
- [ ] Env var override: `WHALECLI_ETHERSCAN_API_KEY=abc` overrides config file value
- [ ] `write_default_config()`: file written, is valid TOML
- [ ] `set_config_value()`: updates single key without touching others

### `tests/test_cli.py`

Uses Click's `CliRunner` for integration tests.

Tests must cover:
- [ ] `whalecli --version` → exits 0, contains version string
- [ ] `whalecli wallet add 0x...valid... --chain ETH` → exits 0
- [ ] `whalecli wallet add invalid --chain ETH` → exits 2
- [ ] `whalecli wallet list --format json` → exits 0, valid JSON
- [ ] `whalecli scan --chain ETH --hours 4 --format json` with mocked fetcher → exits 0 or 1
- [ ] `whalecli scan` with no wallets tracked → exits 2 with NO_WALLETS_TRACKED
- [ ] `whalecli config init` → creates config file
- [ ] `whalecli config show --format json` → valid JSON with masked API key
- [ ] Exit codes: `WhaleCLIError` → 2, no alerts → 1, alerts found → 0
