# whalecli — Agent-Native Whale Wallet Tracker

**Track crypto whale movements. Close the loop.**

A CLI tool + OpenClaw agent skill for tracking whale wallet flows on ETH and BTC chains. Designed from the ground up for AI agents — all output is structured JSON/JSONL by default, exit codes are meaningful, and streaming is supported.

## Why Agent-Native?

Most crypto CLI tools are designed for humans first — pretty tables, colorful output, parsed text that's hard for machines to consume. **whalecli** flips this: agents (EvoClaw, Claude, any A2A participant) can call it programmatically without UI scraping.

**The vision:** close the loop from on-chain signal → agent reasoning → prediction market bet (Simmer/Polymarket). When whales move, agents know — and can act.

## Quick Install

```bash
# From PyPI (when published)
uv pip install whalecli

# Development install
git clone https://github.com/clawinfra/whalecli.git
cd whalecli
uv pip install -e .
```

## Quick Start (5 Commands)

```bash
# 1. Initialize config
whalecli config init

# 2. Add API keys
whalecli config set api.etherscan_api_key YOUR_KEY

# 3. Add whale wallets to track
whalecli wallet add 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 --chain ETH --label "Binance Cold"

# 4. Scan for recent activity
whalecli scan --chain ETH --hours 24 --format json

# 5. Set up real-time alerts
whalecli alert set --score 75
```

## CLI Reference

### Wallet Management

```bash
# Add a whale wallet
whalecli wallet add <address> --chain ETH --label "Binance Cold"

# List all tracked wallets
whalecli wallet list

# Remove a wallet
whalecli wallet remove <address>

# Import wallets from CSV (columns: address, chain, label)
whalecli wallet import whales.csv
```

### Scanning

```bash
# Scan all wallets on a chain
whalecli scan --chain ETH --hours 24 --format json

# Scan specific wallet
whalecli scan --wallet 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 --hours 4 --format table

# Scan all wallets with score threshold
whalecli scan --all --threshold 70 --format jsonl

# Scan with custom alert window
whalecli scan --chain BTC --hours 12 --window 1h --format json
```

### Alerts

```bash
# Alert on flow threshold (USD)
whalecli alert set --threshold 1000000 --window 1h

# Alert on whale score
whalecli alert set --score 75

# List active alerts
whalecli alert list

# Stream alerts continuously
whalecli stream --chain ETH --interval 60 --format jsonl
```

### Reporting

```bash
# Generate wallet report
whalecli report --wallet 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 --days 30 --format json

# Summary report across all wallets
whalecli report --summary --days 7

# CSV export
whalecli report --wallet <addr> --days 30 --format csv > flows.csv
```

### Configuration

```bash
# Initialize config
whalecli config init

# Set config values
whalecli config set api.etherscan_api_key YOUR_KEY
whalecli config set alert_webhook https://hooks.example.com/whale

# Show current config
whalecli config show
```

## Agent Integration

### How Agents Call whalecli

```python
import subprocess
import json

# Scan for whale activity
result = subprocess.run(
    ["whalecli", "scan", "--chain", "ETH", "--hours", "24", "--format", "json"],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    data = json.loads(result.stdout)
    for wallet in data["wallets"]:
        if wallet["score"] > 70:
            # Trigger prediction market bet
            place_bet(wallet["direction"])
```

### Parsing JSONL Streams

```python
import json

# Streaming alerts
process = subprocess.Popen(
    ["whalecli", "stream", "--chain", "ETH", "--interval", "60", "--format", "jsonl"],
    stdout=subprocess.PIPE,
    text=True
)

for line in process.stdout:
    event = json.loads(line)
    if event["type"] == "whale_alert":
        handle_whale_movement(event)
```

### Exit Codes

- `0` — Success
- `1` — CLI error (invalid args, file not found)
- `2` — API error (rate limit, invalid key)
- `3` — Network error (timeout, connection failed)
- `4` — Data error (invalid address, no transactions found)

Agents can use exit codes for conditional logic:

```bash
whalecli scan --chain ETH --hours 24
if [ $? -eq 0 ]; then
    # Process results
fi
```

## Data Sources

### Ethereum (ETH)
- **Etherscan API** — Transaction history, token transfers, internal txns
- **Rate limits:** 5 calls/sec (free tier)
- **Required:** `etherscan_api_key` in config

### Bitcoin (BTC)
- **Mempool.space API** — Mempool transactions, fee estimates
- **Blockchain.info** — Historical transaction data
- **No API key required**

### Hyperliquid (HL)
- **Hyperliquid API** — Perpetual futures flows
- **No API key required**

## Configuration

Config file: `~/.whalecli/config.toml`

```toml
[api]
etherscan_api_key = "YOUR_KEY"
blockchain_info_api_key = ""  # Optional

[alert]
score_threshold = 70
flow_threshold_usd = 1000000
window_minutes = 60
webhook_url = "https://hooks.example.com/whale"

[database]
path = "~/.whalecli/whale.db"
cache_ttl_hours = 24

[output]
default_format = "json"
timezone = "UTC"
```

## Output Formats

### JSON (default)
```json
{
  "wallets": [
    {
      "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
      "chain": "ETH",
      "label": "Binance Cold",
      "score": 85,
      "net_flow_usd": 15000000,
      "tx_count": 42,
      "last_activity": "2026-02-22T09:44:00Z"
    }
  ],
  "scan_time": "2026-02-22T09:44:00Z"
}
```

### JSONL (streaming)
```json
{"type": "scan_start", "timestamp": "2026-02-22T09:44:00Z"}
{"type": "wallet_scan", "address": "0x...", "score": 85}
{"type": "scan_end", "wallets_scanned": 10, "alerts_triggered": 3}
```

### Table (human-readable)
```
┌─────────────────────┬──────┬──────────────┬───────┬──────────────┬─────────────────────┐
│ Address             │ Chain│ Label        │ Score │ Net Flow (USD)│ Last Activity       │
├─────────────────────┼──────┼──────────────┼───────┼──────────────┼─────────────────────┤
│ 0xd8dA...96045      │ ETH  │ Binance Cold │ 85    │ +15,000,000  │ 2026-02-22 09:44:00 │
└─────────────────────┴──────┴──────────────┴───────┴──────────────┴─────────────────────┘
```

## Contributing

See `docs/ARCHITECTURE.md` for system design and `docs/MODULES.md` for code structure.

**Development setup:**
```bash
git clone git@github-alexchen:clawinfra/whalecli.git
cd whalecli
uv pip install -e ".[dev]"
pytest
```

**ClawInfra standards:**
- Documentation first (this repo)
- Test-driven development (coverage ≥ 90%)
- Type-safe (full type annotations)
- CI must be green before merge

## License

MIT License — see `LICENSE` file.

## Links

- GitHub: https://github.com/clawinfra/whalecli
- Docs: `docs/` directory
- Issues: https://github.com/clawinfra/whalecli/issues
