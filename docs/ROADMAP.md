# WhaleWatch CLI — Roadmap

This document outlines the phased delivery plan for `whalecli`. Each phase builds on the previous and has clear acceptance criteria.

---

## Phase 1: Core Tracker + OpenClaw Skill
**Target:** `v0.1.0` — MVP  
**Timeline:** 2–3 weeks from start

### Objectives

Close the primary loop: add a wallet, scan it, get a whale alert, feed it to an agent.

### Deliverables

#### ETH Tracking (`fetchers/eth.py`)
- [ ] Etherscan `txlist` integration (confirmed transactions)
- [ ] Etherscan `tokentx` integration (ERC-20 token transfers)
- [ ] Etherscan `txlistinternal` integration (internal contract calls)
- [ ] USD conversion via CoinGecko price API
- [ ] Auto-pagination for wallets with high transaction volume
- [ ] Cache-aside with SQLite (60s TTL)

#### BTC Tracking (`fetchers/btc.py`)
- [ ] Mempool.space address endpoint integration
- [ ] Blockchain.info fallback
- [ ] BTC/USD price from CoinGecko
- [ ] Address validation (P2PKH, P2SH, bech32)

#### Whale Scoring (`scorer.py`)
- [ ] Net flow score (30%)
- [ ] Velocity score with 30-day baseline (25%)
- [ ] Correlation score (25%)
- [ ] Exchange flow score with known exchange addresses (20%)
- [ ] Final weighted score, 0–100

#### Alert Engine (`alert.py`)
- [ ] Score threshold alerting (>70)
- [ ] USD value threshold alerting
- [ ] Alert deduplication (1h window)
- [ ] Alert persistence to SQLite

#### CLI Commands
- [ ] `wallet add / list / remove / import`
- [ ] `scan` (all options)
- [ ] `alert` + `alert list`
- [ ] `stream` (JSONL)
- [ ] `report` (single wallet + fleet summary)
- [ ] `config init / set / show`

#### OpenClaw Skill
- [ ] `skill/whalecli_skill.py` wrapper
- [ ] EvoClaw registration example
- [ ] FearHarvester workflow prototype

#### Infrastructure
- [ ] `pyproject.toml` with all dependencies
- [ ] GitHub Actions CI: lint + test on push
- [ ] `pytest` test suite, coverage ≥ 90%
- [ ] SQLite schema v1 with migrations

### Acceptance Criteria

1. `whalecli wallet add 0x... --chain ETH && whalecli scan --chain ETH --hours 24` exits 0 with valid JSON
2. `whalecli stream --interval 60 --format jsonl` emits heartbeat lines and alert lines
3. `whalecli report --summary --days 7 --format json` returns valid summary JSON
4. Test coverage ≥ 90%
5. All CI checks pass
6. OpenClaw skill can parse all outputs without errors

---

## Phase 2: Cloud Mode + Shared Instance
**Target:** `v0.2.0`  
**Timeline:** 3–4 weeks after Phase 1

### Objectives

Allow multiple agents to share one whale tracker instance via a FastAPI server. Enable team setups and EvoClaw cloud deployments.

### Deliverables

#### FastAPI Server (`server/`)
- [ ] `GET /scan` — mirror of `whalecli scan` (returns same JSON schema)
- [ ] `GET /stream` — SSE (Server-Sent Events) stream of JSONL events
- [ ] `POST /wallet` — add wallet
- [ ] `GET /wallet` — list wallets
- [ ] `DELETE /wallet/{address}` — remove wallet
- [ ] `GET /report` — report endpoint
- [ ] `GET /alert` — alert list endpoint
- [ ] API key authentication (bearer token)
- [ ] Rate limiting per API key
- [ ] Docker image + `docker-compose.yml`

#### CLI Cloud Mode
- [ ] `--cloud` flag routes CLI to server instead of direct API calls
- [ ] Config: `[cloud] server_url`, `api_key`
- [ ] `whalecli config set cloud.server_url https://...`
- [ ] Graceful fallback to local if server unreachable

#### Auth & Security
- [ ] API key generation + rotation
- [ ] HTTPS required in production
- [ ] Server-side rate limiting per key + per IP
- [ ] Read-only API keys (for agents) vs admin keys (for wallet management)

#### Deployment
- [ ] Dockerfile
- [ ] `docker-compose.yml` with nginx + SSL termination
- [ ] Deploy guide in `docs/DEPLOYMENT.md`

### Acceptance Criteria

1. `whalecli scan --cloud --format json` returns same output as local mode
2. Multiple simultaneous agent connections (10+) don't degrade performance
3. Server starts with `docker-compose up` in < 30 seconds
4. API key auth blocks unauthorized requests with `401`
5. All existing CLI tests pass in cloud-mode configuration

---

## Phase 3: Simmer/Polymarket Auto-Betting Integration
**Target:** `v0.3.0`  
**Timeline:** 3–4 weeks after Phase 2

### Objectives

Complete the closed loop: whale signal → agent reasoning → automated prediction market bet → outcome tracking → signal quality improvement.

### Deliverables

#### Simmer Integration (`integrations/simmer.py`)
- [ ] Simmer API client (auth, markets list, bet placement)
- [ ] Market selector: given a whale signal, find the most relevant active market
- [ ] Bet sizing: configurable (fixed USD, or % of bankroll)
- [ ] Bet placement: `whalecli bet --simmer --direction LONG --confidence 0.80`
- [ ] Position tracking: monitor open positions

#### Polymarket Integration (`integrations/polymarket.py`)
- [ ] Polymarket CLOB API client
- [ ] Market discovery for crypto price predictions
- [ ] On-chain bet placement (via wallet + private key)
- [ ] USDC position management
- [ ] **Security:** private key handled via env var only, never stored in config

#### Outcome Tracker (`tracker.py`)
- [ ] Log each bet with: timestamp, whale signal, direction, confidence, bet size
- [ ] Poll market resolution
- [ ] Record P/L per bet
- [ ] Compute signal accuracy over rolling 30-day window

#### Scoring Feedback Loop (`scorer.py` update)
- [ ] Read outcome history from tracker
- [ ] Adjust sub-score weights based on which signals historically predicted correct direction
- [ ] Optional: bayesian weight update (documented with math in ARCHITECTURE.md)
- [ ] `whalecli score calibrate` — run calibration and show updated weights

#### CLI Additions
- [ ] `whalecli bet --simmer --direction LONG --confidence 0.80 --usd 100`
- [ ] `whalecli bet list` — show open positions
- [ ] `whalecli bet history` — show completed bets with P/L
- [ ] `whalecli score calibrate` — recalibrate weights from history

### Acceptance Criteria

1. `whalecli bet --simmer` places a test bet and returns a valid bet ID
2. `whalecli bet history` returns bet records with P/L
3. After 30 days of bets, `whalecli score calibrate` produces updated weights
4. Polymarket integration works with testnet/preview markets
5. Private key is NEVER logged or stored in plaintext

---

## Phase 4: Multi-Chain + DEX Flow Tracking
**Target:** `v0.4.0`  
**Timeline:** 4–6 weeks after Phase 3

### Objectives

Expand beyond ETH/BTC to cover SOL, BNB, and on-chain DEX flows (Uniswap, dYdX, Jupiter). Become the universal whale tracker.

### Deliverables

#### Solana Fetcher (`fetchers/sol.py`)
- [ ] Solana RPC client (public endpoint + configurable custom RPC)
- [ ] SOL transfer history via transaction parsing
- [ ] SPL token transfer support
- [ ] SOL/USD price from CoinGecko
- [ ] Wallet address validation (base58, 32 bytes)
- [ ] Jupiter DEX large swap detection

#### BNB Chain Fetcher (`fetchers/bnb.py`)
- [ ] BscScan API integration (same interface as Etherscan)
- [ ] BEP-20 token transfer support
- [ ] BNB/USD price
- [ ] PancakeSwap large trade detection

#### DEX Flow Tracking (`fetchers/dex.py`)
- [ ] Uniswap v3 subgraph: large swap detection (>$500K)
- [ ] dYdX order book imbalance (indicator, not individual trades)
- [ ] Jupiter aggregator: large SOL/USDC swaps
- [ ] PancakeSwap: large BNB/stablecoin swaps

#### Scoring Updates
- [ ] Chain-specific scoring parameters (BTC velocity different from ETH)
- [ ] DEX flow sub-score (optional 5th dimension)
- [ ] Cross-chain correlation (BTC whale + ETH whale moving = stronger signal)

#### CLI Additions
- [ ] `--chain SOL`, `--chain BNB`, `--chain ALL`
- [ ] `whalecli dex scan --chain ETH --dex uniswap --hours 4`
- [ ] Cross-chain report: `whalecli report --cross-chain --days 7`

#### Infrastructure
- [ ] Per-chain rate limiting (SOL RPC is more generous than Etherscan)
- [ ] Chain-specific exchange address registries (SOL exchanges, BNB exchanges)
- [ ] Expanded test suite covering new chains (mock responses for all APIs)

### Acceptance Criteria

1. `whalecli wallet add <SOL_ADDRESS> --chain SOL` and scan works
2. `whalecli scan --chain ALL --hours 4` returns results from ETH, BTC, SOL, BNB
3. `whalecli dex scan --dex uniswap --hours 1` shows large swaps
4. Test coverage stays ≥ 90% with new chains added
5. Performance: `--chain ALL` scan completes in < 15 seconds (parallel fetching)

---

## Future Ideas (Backlog)

These are not committed to a phase yet but are worth tracking:

- **On-chain options flow** — large BTC/ETH options positions as directional signal
- **NFT whale tracking** — large NFT portfolio moves as market sentiment indicator
- **Wallet clustering** — identify related wallets (same entity, different addresses)
- **Alert webhooks** — POST alert JSON to a user-configured URL
- **Telegram bot mode** — `whalecli serve --telegram --token <BOT_TOKEN>`
- **Browser extension** — show whale score next to any address on Etherscan
- **Historical backtest** — `whalecli backtest --strategy fear-harvester --days 90` evaluates signal accuracy on historical data
- **MCP server** — expose `whalecli` as an MCP tool for Claude Desktop

---

## Versioning Policy

`whalecli` follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (`1.0.0`): Breaking CLI interface changes (flag renames, schema changes)
- **MINOR** (`0.x.0`): New features, new chains, new commands (backward compatible)
- **PATCH** (`0.0.x`): Bug fixes, performance improvements, doc updates

Schema stability guarantee: JSON output schemas are **stable within a minor version**. Field additions are allowed in patches; removals only in minor bumps with deprecation notice.

---

## How to Contribute to the Roadmap

1. Open a GitHub issue tagged `roadmap`
2. Describe the feature and which phase it fits
3. If accepted, it gets added to the relevant phase here
4. Implementation follows documentation-first approach (docs before code)
