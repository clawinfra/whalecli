# API Reference — whalecli

> Complete CLI command reference, JSON schemas, config TOML schema, env vars, and error codes.

---

## Command Reference

### `whalecli wallet`

Manage the tracked wallet registry.

---

#### `whalecli wallet add <address>`

Add a whale wallet to track.

**Flags:**

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `<address>` | string | ✅ | — | Blockchain address (ETH: 0x-prefixed, BTC: base58) |
| `--chain` | string | ✅ | — | Chain identifier: `ETH`, `BTC`, or `HL` |
| `--label` | string | ❌ | `""` | Human-readable label (e.g. "Binance Cold") |
| `--tag` | string (multi) | ❌ | `[]` | Tags for filtering. Repeatable: `--tag exchange --tag binance` |
| `--format` | string | ❌ | `json` | Output format: `json`, `table` |

**Output Schema:**
```json
{
  "status": "added",
  "wallet": {
    "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    "chain": "ETH",
    "label": "Binance Cold",
    "tags": ["exchange", "binance"],
    "added_at": "2026-02-22T09:44:00Z",
    "active": true
  }
}
```

**Example 1: Add an ETH whale with label and tags**
```bash
whalecli wallet add 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 \
  --chain ETH \
  --label "Binance Cold" \
  --tag exchange \
  --tag binance
```
```json
{
  "status": "added",
  "wallet": {
    "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    "chain": "ETH",
    "label": "Binance Cold",
    "tags": ["exchange", "binance"],
    "added_at": "2026-02-22T09:44:00Z",
    "active": true
  }
}
```

**Example 2: Add a BTC whale**
```bash
whalecli wallet add 1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ \
  --chain BTC \
  --label "Satoshi era wallet"
```
```json
{
  "status": "added",
  "wallet": {
    "address": "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ",
    "chain": "BTC",
    "label": "Satoshi era wallet",
    "tags": [],
    "added_at": "2026-02-22T09:44:00Z",
    "active": true
  }
}
```

**Error: Duplicate wallet**
```json
{
  "error": "wallet_exists",
  "message": "Address 0xd8dA...96045 on ETH is already tracked",
  "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
  "chain": "ETH"
}
```

Exit code: `4` on error, `0` on success.

---

#### `whalecli wallet list`

List all tracked wallets.

**Flags:**

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--chain` | string | ❌ | all | Filter by chain: `ETH`, `BTC`, `HL` |
| `--tag` | string (multi) | ❌ | `[]` | Filter by tag |
| `--format` | string | ❌ | `json` | `json`, `table`, `csv` |

**Output Schema:**
```json
{
  "count": 2,
  "wallets": [
    {
      "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
      "chain": "ETH",
      "label": "Binance Cold",
      "tags": ["exchange", "binance"],
      "added_at": "2026-02-22T09:44:00Z",
      "first_seen": "2017-11-28T00:00:00Z",
      "active": true
    },
    {
      "address": "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ",
      "chain": "BTC",
      "label": "Satoshi era wallet",
      "tags": [],
      "added_at": "2026-02-22T09:44:00Z",
      "first_seen": "2009-01-12T00:00:00Z",
      "active": true
    }
  ]
}
```

**Example 1: List all wallets as JSON**
```bash
whalecli wallet list
```
```json
{
  "count": 2,
  "wallets": [...]
}
```

**Example 2: List only ETH wallets as table**
```bash
whalecli wallet list --chain ETH --format table
```
```
┌──────────────────────────────────────────────┬───────┬──────────────┬────────────────────────┐
│ Address                                      │ Chain │ Label        │ Added                  │
├──────────────────────────────────────────────┼───────┼──────────────┼────────────────────────┤
│ 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 │ ETH   │ Binance Cold │ 2026-02-22 09:44:00 UTC │
└──────────────────────────────────────────────┴───────┴──────────────┴────────────────────────┘
```

---

#### `whalecli wallet remove <address>`

Remove a tracked wallet (marks inactive; does not delete tx history).

**Flags:**

| Flag | Type | Required | Description |
|---|---|---|---|
| `<address>` | string | ✅ | Wallet address to remove |
| `--chain` | string | ✅ | Chain identifier |
| `--purge` | flag | ❌ | Also delete all cached transactions for this wallet |

**Output Schema:**
```json
{
  "status": "removed",
  "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
  "chain": "ETH"
}
```

**Example 1: Remove wallet (keep history)**
```bash
whalecli wallet remove 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 --chain ETH
```
```json
{"status": "removed", "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "chain": "ETH"}
```

**Example 2: Remove wallet and purge all cached data**
```bash
whalecli wallet remove 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 --chain ETH --purge
```
```json
{"status": "removed", "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "chain": "ETH", "transactions_deleted": 1247}
```

---

#### `whalecli wallet import <file>`

Import wallets from a CSV file.

**CSV format:**
```
address,chain,label,tags
0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045,ETH,Binance Cold,"exchange,binance"
1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ,BTC,Satoshi,""
```

**Output Schema:**
```json
{
  "imported": 2,
  "skipped": 0,
  "errors": [],
  "wallets": [...]
}
```

**Example 1: Import from file**
```bash
whalecli wallet import whales.csv
```
```json
{"imported": 10, "skipped": 2, "errors": [], "wallets": [...]}
```

**Example 2: Import with dry run**
```bash
whalecli wallet import whales.csv --dry-run
```
```json
{"would_import": 10, "would_skip": 2, "validation_errors": []}
```

---

### `whalecli scan`

Scan tracked wallets for recent whale activity and compute scores.

**Flags:**

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--chain` | string | ❌ | all | Filter by chain: `ETH`, `BTC`, `HL` |
| `--wallet` | string | ❌ | — | Scan single wallet address |
| `--all` | flag | ❌ | — | Scan all tracked wallets |
| `--hours` | integer | ❌ | `24` | Look-back window in hours |
| `--threshold` | integer | ❌ | `0` | Only return wallets with score ≥ threshold |
| `--format` | string | ❌ | `json` | `json`, `jsonl`, `table`, `csv` |
| `--no-cache` | flag | ❌ | — | Force fresh API fetch, bypass cache |

> **Note:** At least one of `--chain`, `--wallet`, or `--all` must be provided.

**Output Schema (JSON format):**
```json
{
  "scan_id": "scan_20260222_094400_a3f2",
  "scan_time": "2026-02-22T09:44:00Z",
  "chain": "ETH",
  "window_hours": 24,
  "wallets_scanned": 5,
  "alerts_triggered": 2,
  "wallets": [
    {
      "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
      "chain": "ETH",
      "label": "Binance Cold",
      "score": 85,
      "score_breakdown": {
        "net_flow": 35,
        "velocity": 22,
        "correlation": 18,
        "exchange_flow": 10
      },
      "direction": "accumulating",
      "net_flow_usd": 15750000.0,
      "inflow_usd": 22300000.0,
      "outflow_usd": 6550000.0,
      "tx_count": 42,
      "last_activity": "2026-02-22T08:12:34Z",
      "alert_triggered": true
    }
  ]
}
```

**Output Schema (JSONL format) — one JSON object per line:**
```jsonl
{"type":"scan_start","scan_id":"scan_20260222_094400_a3f2","timestamp":"2026-02-22T09:44:00Z","chain":"ETH","window_hours":24}
{"type":"wallet_result","address":"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045","chain":"ETH","label":"Binance Cold","score":85,"direction":"accumulating","net_flow_usd":15750000.0,"alert_triggered":true,"timestamp":"2026-02-22T09:44:01Z"}
{"type":"wallet_result","address":"0x742d35Cc6634C0532925a3b8D4C9C4c2e44B63b5","chain":"ETH","label":"FTX Recovery","score":42,"direction":"distributing","net_flow_usd":-3200000.0,"alert_triggered":false,"timestamp":"2026-02-22T09:44:02Z"}
{"type":"scan_end","scan_id":"scan_20260222_094400_a3f2","wallets_scanned":5,"alerts_triggered":2,"timestamp":"2026-02-22T09:44:05Z"}
```

**Example 1: Scan all ETH wallets, last 24h, JSON output**
```bash
whalecli scan --chain ETH --hours 24 --format json
```
```json
{
  "scan_id": "scan_20260222_094400_a3f2",
  "scan_time": "2026-02-22T09:44:00Z",
  "chain": "ETH",
  "window_hours": 24,
  "wallets_scanned": 5,
  "alerts_triggered": 2,
  "wallets": [...]
}
```

**Example 2: Scan single wallet with score threshold, JSONL**
```bash
whalecli scan --wallet 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 \
  --hours 4 \
  --threshold 60 \
  --format jsonl
```
```jsonl
{"type":"scan_start","scan_id":"scan_20260222_094401_b8c1","timestamp":"2026-02-22T09:44:01Z","chain":"ETH","window_hours":4}
{"type":"wallet_result","address":"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045","score":85,...}
{"type":"scan_end","wallets_scanned":1,"alerts_triggered":1,"timestamp":"2026-02-22T09:44:03Z"}
```

---

### `whalecli alert`

Configure and view alerts.

---

#### `whalecli alert` (set alert rule)

Set a new alert rule. Rules are evaluated after every scan.

**Flags:**

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--threshold` | float | ❌ | — | Alert when net_flow_usd exceeds this amount |
| `--score` | integer | ❌ | — | Alert when whale score exceeds this value (0–100) |
| `--window` | string | ❌ | `1h` | Time window: `15m`, `30m`, `1h`, `4h`, `24h` |
| `--chain` | string | ❌ | all | Apply rule to specific chain only |
| `--webhook` | string | ❌ | — | Override webhook URL for this rule |
| `--format` | string | ❌ | `json` | `json`, `table` |

**Output Schema:**
```json
{
  "status": "alert_configured",
  "rule": {
    "id": "rule_001",
    "type": "score",
    "value": 75,
    "window": "1h",
    "chain": "ETH",
    "webhook_url": "https://hooks.example.com/whale",
    "created_at": "2026-02-22T09:44:00Z",
    "active": true
  }
}
```

**Example 1: Alert on score ≥ 75 for ETH wallets**
```bash
whalecli alert --score 75 --chain ETH
```
```json
{
  "status": "alert_configured",
  "rule": {
    "id": "rule_001",
    "type": "score",
    "value": 75,
    "window": "1h",
    "chain": "ETH",
    "webhook_url": null,
    "created_at": "2026-02-22T09:44:00Z",
    "active": true
  }
}
```

**Example 2: Alert on $1M+ flow in 1h with webhook**
```bash
whalecli alert --threshold 1000000 --window 1h \
  --webhook https://hooks.example.com/whale-alert
```
```json
{
  "status": "alert_configured",
  "rule": {
    "id": "rule_002",
    "type": "flow",
    "value": 1000000,
    "window": "1h",
    "chain": null,
    "webhook_url": "https://hooks.example.com/whale-alert",
    "created_at": "2026-02-22T09:44:00Z",
    "active": true
  }
}
```

---

#### `whalecli alert list`

List all configured alert rules and recent alert history.

**Output Schema:**
```json
{
  "rules": [
    {
      "id": "rule_001",
      "type": "score",
      "value": 75,
      "window": "1h",
      "chain": "ETH",
      "active": true,
      "created_at": "2026-02-22T09:44:00Z"
    }
  ],
  "recent_alerts": [
    {
      "id": "alert_20260222_001",
      "rule_id": "rule_001",
      "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
      "chain": "ETH",
      "score": 85,
      "triggered_at": "2026-02-22T09:00:00Z",
      "webhook_sent": true,
      "webhook_status": 200
    }
  ]
}
```

**Example 1: List all rules and recent alerts**
```bash
whalecli alert list
```
```json
{"rules": [...], "recent_alerts": [...]}
```

**Example 2: List as table**
```bash
whalecli alert list --format table
```
```
Active Rules:
┌──────────┬───────┬───────┬────────┬───────┐
│ ID       │ Type  │ Value │ Window │ Chain │
├──────────┼───────┼───────┼────────┼───────┤
│ rule_001 │ score │ 75    │ 1h     │ ETH   │
│ rule_002 │ flow  │ 1M    │ 1h     │ all   │
└──────────┴───────┴───────┴────────┴───────┘
```

---

### `whalecli stream`

Stream wallet events continuously as JSONL. Designed for agent consumption — pipe directly into an agent's stdin.

**Flags:**

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--chain` | string | ❌ | all | Chain to stream |
| `--interval` | integer | ❌ | `60` | Polling interval in seconds |
| `--threshold` | integer | ❌ | `70` | Only emit events for wallets with score ≥ this |
| `--format` | string | ❌ | `jsonl` | Always `jsonl` for stream (table/json not meaningful here) |
| `--hours` | integer | ❌ | `1` | Look-back window for each poll cycle |

**JSONL Event Types:**

| `type` | When emitted | Fields |
|---|---|---|
| `stream_start` | Stream begins | `timestamp`, `chain`, `interval_secs` |
| `heartbeat` | Every `interval` seconds (even if no whale activity) | `timestamp`, `cycle`, `wallets_checked` |
| `whale_alert` | Wallet score ≥ threshold | `address`, `chain`, `label`, `score`, `direction`, `net_flow_usd`, `timestamp` |
| `whale_activity` | Any whale moves (below threshold) | Same as `whale_alert` |
| `stream_error` | API error during poll cycle | `error_code`, `message`, `recoverable`, `timestamp` |
| `stream_end` | Stream terminated (SIGINT/SIGTERM) | `timestamp`, `cycles_completed`, `total_alerts` |

**Full JSONL schema — `whale_alert` event:**
```json
{
  "type": "whale_alert",
  "timestamp": "2026-02-22T09:44:30Z",
  "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
  "chain": "ETH",
  "label": "Binance Cold",
  "score": 85,
  "score_breakdown": {
    "net_flow": 35,
    "velocity": 22,
    "correlation": 18,
    "exchange_flow": 10
  },
  "direction": "accumulating",
  "net_flow_usd": 15750000.0,
  "tx_count_in_window": 42,
  "alert_triggered": true,
  "cycle": 3
}
```

**Example 1: Stream ETH alerts every 60 seconds**
```bash
whalecli stream --chain ETH --interval 60 --format jsonl
```
```jsonl
{"type":"stream_start","timestamp":"2026-02-22T09:44:00Z","chain":"ETH","interval_secs":60}
{"type":"heartbeat","timestamp":"2026-02-22T09:44:05Z","cycle":1,"wallets_checked":5}
{"type":"whale_alert","timestamp":"2026-02-22T09:45:05Z","address":"0xd8dA...","chain":"ETH","score":85,...}
{"type":"heartbeat","timestamp":"2026-02-22T09:45:05Z","cycle":2,"wallets_checked":5}
```

**Example 2: Stream all chains, only high-score alerts**
```bash
whalecli stream --interval 120 --threshold 85 --format jsonl
```
```jsonl
{"type":"stream_start","timestamp":"2026-02-22T09:44:00Z","chain":"all","interval_secs":120}
{"type":"heartbeat","timestamp":"2026-02-22T09:44:10Z","cycle":1,"wallets_checked":12}
{"type":"whale_alert","timestamp":"2026-02-22T09:46:12Z","address":"1P5ZED...","chain":"BTC","score":91,...}
```

---

### `whalecli report`

Generate historical reports for wallets.

**Flags:**

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--wallet` | string | ❌ | — | Report for single wallet address |
| `--chain` | string | ❌ | — | Required when `--wallet` used if address could be ambiguous |
| `--days` | integer | ❌ | `7` | Report period in days |
| `--summary` | flag | ❌ | — | Summary report across all tracked wallets |
| `--format` | string | ❌ | `json` | `json`, `table`, `csv` |

> **Note:** Either `--wallet` or `--summary` must be provided.

**Output Schema (wallet report):**
```json
{
  "report_id": "report_20260222_094400",
  "generated_at": "2026-02-22T09:44:00Z",
  "period_days": 30,
  "wallet": {
    "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    "chain": "ETH",
    "label": "Binance Cold"
  },
  "summary": {
    "total_inflow_usd": 340000000.0,
    "total_outflow_usd": 285000000.0,
    "net_flow_usd": 55000000.0,
    "peak_score": 91,
    "avg_score": 67,
    "alerts_triggered": 8,
    "dominant_direction": "accumulating",
    "tx_count": 1842
  },
  "daily_breakdown": [
    {
      "date": "2026-02-22",
      "inflow_usd": 22300000.0,
      "outflow_usd": 6550000.0,
      "net_flow_usd": 15750000.0,
      "score": 85,
      "tx_count": 42
    }
  ],
  "top_counterparties": [
    {
      "address": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
      "label": "Uniswap V3",
      "volume_usd": 45000000.0,
      "tx_count": 128,
      "direction": "outflow"
    }
  ]
}
```

**Output Schema (summary report):**
```json
{
  "report_id": "summary_20260222_094400",
  "generated_at": "2026-02-22T09:44:00Z",
  "period_days": 7,
  "total_wallets": 12,
  "wallets": [
    {
      "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
      "chain": "ETH",
      "label": "Binance Cold",
      "net_flow_usd": 55000000.0,
      "peak_score": 91,
      "alerts_triggered": 8,
      "dominant_direction": "accumulating"
    }
  ],
  "aggregate": {
    "total_net_flow_usd": 180000000.0,
    "dominant_direction": "accumulating",
    "most_active_chain": "ETH",
    "total_alerts": 23
  }
}
```

**Example 1: 30-day wallet report as JSON**
```bash
whalecli report \
  --wallet 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 \
  --days 30 \
  --format json
```
```json
{"report_id": "report_20260222_094400", "period_days": 30, ...}
```

**Example 2: 7-day summary as CSV**
```bash
whalecli report --summary --days 7 --format csv > report.csv
```
```
address,chain,label,net_flow_usd,peak_score,alerts_triggered,dominant_direction
0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045,ETH,Binance Cold,55000000.0,91,8,accumulating
1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ,BTC,Satoshi era wallet,2100000.0,74,2,accumulating
```

---

### `whalecli config`

Manage configuration.

---

#### `whalecli config init`

Initialize default config at `~/.whalecli/config.toml`.

**Output:**
```json
{
  "status": "initialized",
  "config_path": "/home/user/.whalecli/config.toml"
}
```

**Example 1:**
```bash
whalecli config init
```
```json
{"status": "initialized", "config_path": "/home/alex/.whalecli/config.toml"}
```

**Example 2: Force reinitialize (overwrites existing)**
```bash
whalecli config init --force
```
```json
{"status": "reinitialized", "config_path": "/home/alex/.whalecli/config.toml", "backup": "/home/alex/.whalecli/config.toml.bak"}
```

---

#### `whalecli config set <key> <value>`

Set a config value by dotted key path.

**Example 1: Set API key**
```bash
whalecli config set api.etherscan_api_key ABCDEF123456
```
```json
{"status": "updated", "key": "api.etherscan_api_key", "value": "AB...56"}
```

**Example 2: Set score threshold**
```bash
whalecli config set alert.score_threshold 80
```
```json
{"status": "updated", "key": "alert.score_threshold", "value": 80}
```

---

#### `whalecli config show`

Show current config. API keys are masked.

**Output Schema:**
```json
{
  "config_path": "/home/alex/.whalecli/config.toml",
  "api": {
    "etherscan_api_key": "AB...56",
    "blockchain_info_api_key": null
  },
  "alert": {
    "score_threshold": 70,
    "flow_threshold_usd": 1000000,
    "window_minutes": 60,
    "webhook_url": "https://hooks.example.com/whale"
  },
  "database": {
    "path": "~/.whalecli/whale.db",
    "cache_ttl_hours": 24
  },
  "output": {
    "default_format": "json",
    "timezone": "UTC"
  },
  "cloud": {
    "enabled": false,
    "url": null
  }
}
```

**Example 1:**
```bash
whalecli config show
```

**Example 2: Show as table**
```bash
whalecli config show --format table
```

---

## Config TOML Schema

Full schema for `~/.whalecli/config.toml`:

```toml
# API configuration
[api]
etherscan_api_key = ""           # Required for ETH scans. Get from https://etherscan.io/apis
blockchain_info_api_key = ""     # Optional. Blockchain.info API key for higher rate limits.
hyperliquid_api_key = ""         # Optional. Leave empty; HL API is public.

# Alert configuration
[alert]
score_threshold = 70             # integer, 0-100. Scores >= this trigger alerts.
flow_threshold_usd = 1000000     # float, USD. Net flow > this triggers flow alerts.
window_minutes = 60              # integer. Rolling window for flow threshold calculation.
webhook_url = ""                 # string. HTTP POST target for alert payloads.
webhook_secret = ""              # string. Optional HMAC secret for webhook signature.

# Database / cache
[database]
path = "~/.whalecli/whale.db"   # string. SQLite database path. Tilde expanded.
cache_ttl_hours = 24             # integer. Default TTL for historical tx cache.

# Output defaults
[output]
default_format = "json"          # string: "json" | "jsonl" | "table" | "csv"
timezone = "UTC"                 # string. IANA timezone for display timestamps.
color = true                     # bool. Enable rich/color output in table format.

# Cloud mode (Phase 2)
[cloud]
enabled = false                  # bool. When true, routes all commands to cloud backend.
url = ""                         # string. Cloud backend URL.
api_token = ""                   # string. JWT from `whalecli auth login`.
```

---

## Environment Variables

All config values can be overridden via environment variables. Env vars take precedence over `config.toml`.

| Env Var | Corresponding Config Key | Notes |
|---|---|---|
| `WHALECLI_ETHERSCAN_API_KEY` | `api.etherscan_api_key` | — |
| `WHALECLI_BLOCKCHAIN_INFO_KEY` | `api.blockchain_info_api_key` | — |
| `WHALECLI_HYPERLIQUID_KEY` | `api.hyperliquid_api_key` | — |
| `WHALECLI_SCORE_THRESHOLD` | `alert.score_threshold` | integer |
| `WHALECLI_FLOW_THRESHOLD_USD` | `alert.flow_threshold_usd` | float |
| `WHALECLI_WEBHOOK_URL` | `alert.webhook_url` | — |
| `WHALECLI_DB_PATH` | `database.path` | — |
| `WHALECLI_CACHE_TTL_HOURS` | `database.cache_ttl_hours` | integer |
| `WHALECLI_OUTPUT_FORMAT` | `output.default_format` | — |
| `WHALECLI_TIMEZONE` | `output.timezone` | IANA name |
| `WHALECLI_CLOUD_ENABLED` | `cloud.enabled` | `"true"` or `"false"` |
| `WHALECLI_CLOUD_URL` | `cloud.url` | — |
| `WHALECLI_CLOUD_TOKEN` | `cloud.api_token` | — |
| `WHALECLI_CONFIG_PATH` | — | Override config file location entirely |
| `WHALECLI_NO_COLOR` | — | Disable rich output regardless of config |

---

## Error Codes

All errors are returned as JSON on stdout with a non-zero exit code.

**Standard error payload:**
```json
{
  "error": "<error_code>",
  "message": "<human readable description>",
  "details": { }
}
```

### Exit Codes

| Exit Code | Meaning | When |
|---|---|---|
| `0` | Success | Command completed successfully |
| `1` | CLI error | Invalid arguments, missing required flags, file not found |
| `2` | API error | Invalid API key, rate limit exceeded, upstream 4xx/5xx |
| `3` | Network error | Timeout, connection refused, DNS failure |
| `4` | Data error | Invalid address format, no transactions found, wallet not tracked |
| `5` | Config error | Config file missing, malformed TOML, invalid values |
| `6` | Database error | SQLite error, permission denied, disk full |

### Error Codes (string field)

| Error Code | Exit | Description |
|---|---|---|
| `invalid_address` | 4 | Address format invalid for chain |
| `wallet_not_found` | 4 | Address not in tracked wallet list |
| `wallet_exists` | 4 | Wallet already tracked (on `wallet add`) |
| `no_transactions` | 4 | No transactions found in window |
| `invalid_api_key` | 2 | Etherscan/other API returned 401 |
| `rate_limited` | 2 | API rate limit hit; retry after delay |
| `api_error` | 2 | Upstream API returned unexpected error |
| `network_timeout` | 3 | Request timed out |
| `connection_failed` | 3 | Could not connect to API |
| `config_missing` | 5 | Config file not found; run `whalecli config init` |
| `config_invalid` | 5 | TOML parse error in config file |
| `db_error` | 6 | SQLite operation failed |

**Example error response:**
```json
{
  "error": "rate_limited",
  "message": "Etherscan API rate limit exceeded. Retry after 60 seconds.",
  "details": {
    "api": "etherscan",
    "retry_after_seconds": 60,
    "plan": "free_tier"
  }
}
```

---

## Webhook Payload Schema

When `webhook_url` is configured, whalecli sends an HTTP POST with `Content-Type: application/json`:

```json
{
  "schema_version": "1",
  "event_type": "whale_alert",
  "triggered_at": "2026-02-22T09:44:30Z",
  "rule": {
    "id": "rule_001",
    "type": "score",
    "value": 75
  },
  "wallet": {
    "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    "chain": "ETH",
    "label": "Binance Cold"
  },
  "score": 85,
  "score_breakdown": {
    "net_flow": 35,
    "velocity": 22,
    "correlation": 18,
    "exchange_flow": 10
  },
  "direction": "accumulating",
  "net_flow_usd": 15750000.0,
  "alert_id": "alert_20260222_001"
}
```

**Signature:** If `webhook_secret` is configured, an `X-Whalecli-Signature` header is added:
```
X-Whalecli-Signature: sha256=<HMAC-SHA256 of body using secret>
```

Recipients should verify this signature before trusting the payload.
