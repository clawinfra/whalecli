# Module Structure — whalecli

Exact file layout for the whalecli project.

## Directory Layout

```
whalecli/
├── README.md                      # Root documentation
├── LICENSE                        # MIT License
├── .gitignore                     # Git ignore rules
├── pyproject.toml                 # Project configuration
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI
│
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md            # System architecture
│   ├── API.md                     # CLI API reference
│   ├── SKILL.md                   # OpenClaw agent skill spec
│   ├── ROADMAP.md                 # Phased delivery plan
│   └── MODULES.md                 # This file
│
├── whalecli/                      # Main package
│   ├── __init__.py                # Package init, version export
│   ├── cli.py                     # Click entry point, all commands
│   ├── config.py                  # Config loading (TOML + env vars)
│   ├── db.py                      # SQLite state management
│   ├── scorer.py                  # Whale score algorithm (0-100)
│   ├── alert.py                   # Threshold detection, webhooks
│   ├── stream.py                  # JSONL streaming, polling loop
│   ├── output.py                  # Format routing (json/table/csv)
│   │
│   ├── fetchers/                  # Data source clients
│   │   ├── __init__.py            # Fetcher package init
│   │   ├── eth.py                 # Etherscan API client
│   │   ├── btc.py                 # Mempool.space + Blockchain.info
│   │   └── hl.py                  # Hyperliquid perp flows
│   │
│   └── skill/                     # OpenClow agent skill
│       ├── __init__.py            # Skill package init
│       ├── whalecli_skill.py      # Skill entry point
│       └── SKILL.md               # Skill documentation (copy from docs/)
│
├── tests/                         # Test suite
│   ├── __init__.py                # Test package init
│   ├── conftest.py                # Pytest fixtures
│   ├── test_config.py             # Config loading tests
│   ├── test_db.py                 # Database operations tests
│   ├── test_scorer.py             # Scoring algorithm tests
│   ├── test_alert.py              # Alert detection tests
│   ├── test_fetchers.py           # API client tests (mocked)
│   │   ├── test_eth_fetcher.py
│   │   ├── test_btc_fetcher.py
│   │   └── test_hl_fetcher.py
│   ├── test_stream.py             # Streaming tests
│   ├── test_output.py             # Format routing tests
│   └── test_cli.py                # End-to-end CLI tests
│
└── examples/                      # Example scripts
    ├── basic_scan.py              # Basic whale scan
    ├── stream_alerts.py           # Real-time alert streaming
    └── agent_integration.py       # Agent integration example
```

## Module Responsibilities

### `whalecli/__init__.py`

**Purpose:** Package initialization, version export.

**Exports:**
```python
__version__ = "0.1.0"
__author__ = "clawinfra"
```

---

### `whalecli/cli.py`

**Purpose:** Click entry point, all CLI commands.

**Key Functions:**
- `cli()` — Main entry point
- `wallet_commands()` — Wallet management subcommands
  - `wallet_add()`
  - `wallet_list()`
  - `wallet_remove()`
  - `wallet_import()`
- `scan_command()` — Scan orchestration
- `alert_command()` — Alert configuration
  - `alert_config()`
  - `alert_list()`
- `stream_command()` — Continuous monitoring
- `report_command()` — Report generation
- `config_command()` — Configuration management
  - `config_init()`
  - `config_set()`
  - `config_show()`

**Dependencies:**
- `click` — CLI framework
- `config.py` — Load config
- `db.py` — Database operations
- `fetchers/` — Data fetching
- `scorer.py` — Calculate scores
- `alert.py` — Check thresholds
- `output.py` — Format results

---

### `whalecli/config.py`

**Purpose:** Configuration loading from TOML + environment variables.

**Key Functions:**
- `load_config(path: str | None = None) -> Config` — Load config from file
- `validate_config(config: Config) -> bool` — Validate API keys, paths
- `get_api_key(provider: str) -> str` — Retrieve API key with fallback
- `init_config() -> Path` — Create default config file

**Data Structures:**
```python
@dataclass
class Config:
    api: ApiConfig
    alert: AlertConfig
    database: DatabaseConfig
    output: OutputConfig

@dataclass
class ApiConfig:
    etherscan_api_key: str
    blockchain_info_api_key: str = ""

@dataclass
class AlertConfig:
    score_threshold: int = 70
    flow_threshold_usd: float = 1_000_000
    window_minutes: int = 60
    webhook_url: str = ""

@dataclass
class DatabaseConfig:
    path: str = "~/.whalecli/whale.db"
    cache_ttl_hours: int = 24

@dataclass
class OutputConfig:
    default_format: str = "json"
    timezone: str = "UTC"
```

**Dependencies:**
- `toml` — TOML parsing
- `pathlib` — Path handling
- `os` — Environment variables

---

### `whalecli/db.py`

**Purpose:** SQLite state management (wallets, transactions, alerts).

**Key Functions:**
- `init_db(path: str) -> sqlite3.Connection` — Create tables if not exist
- `add_wallet(address: str, chain: str, label: str | None)` — Add wallet
- `list_wallets(chain: str | None = None) -> List[Wallet]` — List wallets
- `remove_wallet(address: str)` — Remove wallet
- `cache_transaction(tx: Transaction)` — Cache transaction
- `get_cached_transactions(address: str, hours: int) -> List[Transaction]` — Get cached
- `log_alert(alert: Alert)` — Log alert to database
- `get_alert_history(limit: int = 100) -> List[Alert]` — Get alert history

**Data Structures:**
```python
@dataclass
class Wallet:
    id: int
    address: str
    chain: str
    label: str | None
    added_at: datetime

@dataclass
class Transaction:
    tx_hash: str
    wallet_address: str
    chain: str
    timestamp: datetime
    amount_usd: float
    direction: Literal["in", "out"]
    raw_json: str

@dataclass
class Alert:
    id: int
    wallet_address: str
    score: int
    flow_usd: float
    triggered_at: datetime
    details: str
```

**Dependencies:**
- `sqlite3` — Database
- `aiosqlite` — Async database operations (for streaming)

---

### `whalecli/fetchers/eth.py`

**Purpose:** Etherscan API client for Ethereum data.

**Key Functions:**
- `fetch_transactions(address: str, hours: int, api_key: str) -> List[Transaction]` — Get recent txns
- `fetch_token_transfers(address: str, hours: int, api_key: str) -> List[Transaction]` — Get ERC-20 transfers
- `calculate_usd_value(tx: dict, prices: dict) -> float` — Convert ETH/tokens to USD
- `validate_address(address: str) -> bool` — Validate ETH address format

**Data Structures:**
```python
@dataclass
class EtherscanResponse:
    status: str
    message: str
    result: List[dict]
```

**Dependencies:**
- `httpx` — HTTP client
- `asyncio` — Async requests

**API Endpoints:**
- `https://api.etherscan.io/api?module=account&action=txlist&address={addr}&apikey={key}`
- `https://api.etherscan.io/api?module=account&action=tokentx&address={addr}&apikey={key}`

---

### `whalecli/fetchers/btc.py`

**Purpose:** Mempool.space + Blockchain.info client for Bitcoin data.

**Key Functions:**
- `fetch_transactions(address: str, hours: int) -> List[Transaction]` — Get recent txns
- `calculate_usd_value(tx: dict) -> float` — Convert BTC to USD
- `validate_address(address: str) -> bool` — Validate BTC address format

**Dependencies:**
- `httpx` — HTTP client

**API Endpoints:**
- `https://mempool.space/api/address/{address}` — Address details
- `https://blockchain.info/rawaddr/{address}` — Transaction history

---

### `whalecli/fetchers/hl.py`

**Purpose:** Hyperliquid API client for perpetual futures flows.

**Key Functions:**
- `fetch_flows(hours: int) -> List[Transaction]` — Get large perp flows
- `detect_whale_position_change(position: dict) -> float` — Score position changes
- `get_current_prices() -> dict` — Get mid prices

**Dependencies:**
- `httpx` — HTTP client

**API Endpoints:**
- `https://api.hyperliquid.xyz/info` — Perpetual futures positions
- `https://api.hyperliquid.xyz/allMids` — Mid prices

---

### `whalecli/scorer.py`

**Purpose:** Whale scoring algorithm (0-100).

**Key Functions:**
- `calculate_score(wallet: Wallet, transactions: List[Transaction]) -> ScoreResult` — Main scoring function
- `net_flow_score(wallet: Wallet, transactions: List[Transaction]) -> int` — Net flow score (0-100)
- `velocity_score(transactions: List[Transaction]) -> int` — Velocity score (0-100)
- `correlation_score(wallet: Wallet, all_wallets: List[Wallet]) -> int` — Correlation score (0-100)
- `is_exchange_flow(transaction: Transaction) -> bool` — Check if destination is exchange

**Data Structures:**
```python
@dataclass
class ScoreResult:
    final_score: int
    net_flow_score: int
    velocity_score: int
    correlation_score: int
    is_exchange_flow: bool
    net_flow_usd: float
    inflow_usd: float
    outflow_usd: float
```

**Dependencies:**
- `db.py` — Get historical data for velocity calc
- `fetchers/` — Get price data

---

### `whalecli/alert.py`

**Purpose:** Threshold detection, webhook notifications.

**Key Functions:**
- `check_alerts(scan_results: List[ScoreResult], config: AlertConfig) -> List[Alert]` — Check thresholds
- `trigger_webhook(alert: Alert, webhook_url: str)` — POST to webhook
- `format_alert_message(alert: Alert) -> dict` — Generate alert payload

**Data Structures:**
```python
@dataclass
class Alert:
    wallet_address: str
    score: int
    flow_usd: float
    triggered_at: datetime
    details: str
```

**Dependencies:**
- `httpx` — Webhook requests
- `scorer.py` — Score results

---

### `whalecli/stream.py`

**Purpose:** JSONL streaming, continuous polling.

**Key Functions:**
- `start_stream(chain: str, interval: int, config: Config)` — Main loop
- `emit_event(event: dict)` — Write JSONL to stdout
- `handle_sigint()` — Graceful shutdown

**Data Structures:**
```python
@dataclass
class StreamEvent:
    type: Literal["stream_start", "poll_start", "whale_alert", "poll_end", "stream_end"]
    timestamp: str
    data: dict
```

**Dependencies:**
- `asyncio` — Async polling
- `db.py` — Get wallets
- `fetchers/` — Fetch transactions
- `scorer.py` — Calculate scores
- `alert.py` — Check thresholds

---

### `whalecli/output.py`

**Purpose:** Format routing (json/table/csv).

**Key Functions:**
- `format_json(data: dict) -> str` — Structured JSON
- `format_jsonl(data: List[dict]) -> str` — JSONL lines
- `format_table(data: dict) -> str` — Rich table for terminal
- `format_csv(data: dict) -> str` — CSV for spreadsheets
- `format_output(data: dict, format: str) -> str` — Format router

**Dependencies:**
- `json` — JSON serialization
- `rich` — Table formatting
- `csv` — CSV generation

---

### `whalecli/skill/whalecli_skill.py`

**Purpose:** OpenClaw agent skill entry point.

**Key Functions:**
- `skill_init()` — Initialize skill
- `skill_scan(chain: str, hours: int) -> dict` — Scan from agent
- `skill_stream(chain: str, interval: int) -> Iterator[dict]` — Stream from agent

**Dependencies:**
- `cli.py` — Call whalecli commands

---

### `tests/conftest.py`

**Purpose:** Pytest fixtures for testing.

**Fixtures:**
- `temp_db` — Temporary SQLite database
- `mock_config` — Mock config object
- `mock_etherscan_response` — Mock Etherscan API response
- `sample_wallets` — Sample wallet data
- `sample_transactions` — Sample transaction data

**Dependencies:**
- `pytest` — Test framework
- `pytest-asyncio` — Async test support
- `respx` — HTTP mocking

---

### `tests/test_scorer.py`

**Purpose:** Scoring algorithm tests.

**Test Cases:**
- `test_net_flow_score_high_inflow()` — Test high inflow scenario
- `test_net_flow_score_high_outflow()` — Test high outflow scenario
- `test_velocity_score_surge()` — Test velocity surge detection
- `test_correlation_score_multiple_whales()` — Test correlation detection
- `test_final_score_weighting()` — Test final score calculation
- `test_exchange_flow_detection()` — Test exchange flow detection

**Dependencies:**
- `pytest` — Test framework
- `scorer.py` — Module under test

---

### `tests/test_alert.py`

**Purpose:** Alert detection tests.

**Test Cases:**
- `test_score_threshold_trigger()` — Test score threshold
- `test_flow_threshold_trigger()` — Test flow threshold
- `test_webhook_trigger()` — Test webhook notification
- `test_alert_history_logging()` — Test alert history

**Dependencies:**
- `pytest` — Test framework
- `alert.py` — Module under test
- `respx` — HTTP mocking

---

### `tests/test_fetchers/`

**Purpose:** API client tests (mocked).

**Test Cases (test_eth_fetcher.py):**
- `test_fetch_transactions_success()` — Test successful fetch
- `test_fetch_transactions_rate_limit()` — Test rate limit handling
- `test_validate_address_valid()` — Test valid address
- `test_validate_address_invalid()` — Test invalid address
- `test_calculate_usd_value()` — Test USD conversion

**Dependencies:**
- `pytest` — Test framework
- `respx` — HTTP mocking
- `fetchers/eth.py` — Module under test

---

### `tests/test_cli.py`

**Purpose:** End-to-end CLI tests.

**Test Cases:**
- `test_wallet_add()` — Test wallet add command
- `test_wallet_list()` — Test wallet list command
- `test_scan_command()` — Test scan command
- `test_alert_command()` — Test alert command
- `test_config_init()` — Test config init command
- `test_json_output()` — Test JSON output format
- `test_jsonl_output()` — Test JSONL output format

**Dependencies:**
- `pytest` — Test framework
- `click.testing.CliRunner` — CLI testing
- `cli.py` — Module under test

---

## File Size Estimates

| File | Lines (est.) | Purpose |
|------|--------------|---------|
| `cli.py` | 400 | CLI entry point, all commands |
| `config.py` | 150 | Config loading |
| `db.py` | 250 | Database operations |
| `fetchers/eth.py` | 200 | Etherscan client |
| `fetchers/btc.py` | 150 | BTC client |
| `fetchers/hl.py` | 150 | Hyperliquid client |
| `scorer.py` | 300 | Scoring algorithm |
| `alert.py` | 150 | Alert detection |
| `stream.py` | 200 | Streaming logic |
| `output.py` | 200 | Format routing |
| `skill/whalecli_skill.py` | 150 | Agent skill |

**Total:** ~2,250 lines of Python code (excluding tests)

---

## Import Graph

```
cli.py
├── config.py
├── db.py
├── fetchers/
│   ├── eth.py
│   ├── btc.py
│   └── hl.py
├── scorer.py
│   ├── db.py
│   └── fetchers/
├── alert.py
│   └── scorer.py
├── stream.py
│   ├── db.py
│   ├── fetchers/
│   ├── scorer.py
│   └── alert.py
└── output.py
```

**No circular dependencies** — all imports flow downward.

---

## Extension Points

### Adding a New Chain

1. Create `fetchers/sol.py`
2. Add `--chain SOL` to `cli.py`
3. Update `db.py` validation
4. Add price oracle to `scorer.py`

### Adding a New Output Format

1. Add `format_custom()` to `output.py`
2. Add `--format custom` to `cli.py`

### Adding a New Alert Type

1. Extend `AlertConfig` in `config.py`
2. Add detection logic to `alert.py`
3. Add CLI option to `cli.py`

---

## Next Steps for Builder

1. **Create empty module structure:**
   ```bash
   mkdir -p whalecli/fetchers whalecli/skill tests tests/test_fetchers
   touch whalecli/__init__.py whalecli/cli.py ...
   ```

2. **Implement in order:**
   - `config.py` — Foundation
   - `db.py` — State management
   - `fetchers/` — Data sources
   - `scorer.py` — Core algorithm
   - `cli.py` — Orchestration
   - `alert.py` — Thresholds
   - `stream.py` — Streaming
   - `output.py` — Formatting

3. **Test as you go:**
   - Write tests alongside implementation
   - Maintain ≥ 90% coverage
   - Run `pytest` on every commit

4. **Documentation:**
   - All docs already written (Planner phase complete)
   - Builder should focus on implementation

---

## Notes for Builder

- **Follow ClawInfra standards:** Type-safe, test-driven, coverage ≥ 90%
- **No placeholders:** Decide and implement. If unsure, document in ARCHITECTURE.md
- **Use async:** All fetchers should be async for performance
- **Cache aggressively:** Respect Etherscan rate limits
- **Exit codes matter:** Agents depend on meaningful exit codes
- **JSON by default:** All output should be machine-readable first

Good luck! 🐋
