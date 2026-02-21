# WhaleWatch CLI (whalecli) — Planner Phase Complete

## Summary

Successfully completed the **Planner phase** for the whalecli project. All documentation, architecture, and module structure have been written following ClawInfra standards (documentation-first approach).

## Commit Information

**Commit Hash:** `545591c`
**Commit Message:** docs: complete architecture, API, skill spec, and module design
**Remote:** https://github.com/clawinfra/whalecli

## Deliverables

### 1. Root Documentation
- ✅ **README.md** (6,715 bytes)
  - What whalecli is and why agent-native design matters
  - Quick install instructions
  - Quick start (5 commands from install to first alert)
  - Complete CLI reference
  - Agent integration examples
  - Data sources and configuration
  - Contributing guide

### 2. Architecture Documentation (docs/)
- ✅ **docs/ARCHITECTURE.md** (16,124 bytes)
  - System diagram (ASCII art) showing full data flow
  - Module breakdown with responsibilities
  - Whale scoring algorithm (net flow, velocity, correlation, exchange flow)
  - Local vs Cloud mode differences
  - Database schema (SQLite)
  - Caching strategy
  - Extension points (adding new chains)
  - Error handling and performance considerations

- ✅ **docs/API.md** (17,033 bytes)
  - Complete CLI API reference for every command
  - All flags, arguments, and options documented
  - JSON output schemas with example values
  - JSONL stream format specification
  - Config file schema (TOML)
  - Environment variables
  - Error codes and their meanings

- ✅ **docs/SKILL.md** (13,325 bytes)
  - When agents should invoke the whalecli skill
  - How to call whalecli from Python/shell
  - Parsing JSON/JSONL outputs
  - Exit code handling
  - Integration with FearHarvester/Simmer loop
  - Example agent workflows (morning briefing, real-time alerts, historical analysis)
  - Skill best practices

- ✅ **docs/ROADMAP.md** (8,988 bytes)
  - v0.1 (Foundation) — MVP with ETH/BTC tracking
  - v0.2 (Real-Time) — WebSocket support, prediction market integration
  - v0.3 (Analytics) — ML-based anomaly detection, custom alert rules
  - v0.4 (Cloud) — Multi-user mode with PostgreSQL/Redis
  - v0.5 (Multi-Chain) — Solana, Polygon, Arbitrum support
  - v1.0 (Platform) — Web dashboard, mobile apps

- ✅ **docs/MODULES.md** (16,203 bytes)
  - Exact file layout for entire project
  - Module responsibilities for every file
  - Import graph (no circular dependencies)
  - Extension points (adding chains, output formats, alert types)
  - Notes for Builder

### 3. Module Structure (whalecli/)
- ✅ **whalecli/__init__.py** — Package initialization
- ✅ **whalecli/cli.py** — Click entry point with all commands (placeholder)
- ✅ **whalecli/config.py** — Config loading from TOML + env vars (placeholder)
- ✅ **whalecli/db.py** — SQLite state management (placeholder)
- ✅ **whalecli/scorer.py** — Whale scoring algorithm (placeholder)
- ✅ **whalecli/alert.py** — Threshold detection, webhooks (placeholder)
- ✅ **whalecli/stream.py** — JSONL streaming, polling loop (placeholder)
- ✅ **whalecli/output.py** — Format routing (json/table/csv) (placeholder)
- ✅ **whalecli/fetchers/__init__.py** — Fetcher package
- ✅ **whalecli/fetchers/eth.py** — Etherscan API client (placeholder)
- ✅ **whalecli/fetchers/btc.py** — Mempool.space + Blockchain.info (placeholder)
- ✅ **whalecli/fetchers/hl.py** — Hyperliquid perp flows (placeholder)
- ✅ **whalecli/skill/__init__.py** — Skill package
- ✅ **whalecli/skill/whalecli_skill.py** — OpenClaw agent skill interface

### 4. Project Configuration
- ✅ **pyproject.toml** — Full project configuration
  - Dependencies: click, httpx, rich, toml, aiosqlite
  - Dev dependencies: pytest, pytest-cov, pytest-asyncio, respx
  - CLI entry point: `whalecli = "whalecli.cli:cli"`
  - Test configuration with ≥ 90% coverage requirement
  - Type checking with mypy
  - Formatting with black and isort

### 5. Testing Infrastructure
- ✅ **tests/conftest.py** — Pytest fixtures
  - `temp_db` — Temporary SQLite database
  - `mock_config` — Mock config object
  - `sample_wallets` — Sample wallet data
  - `sample_transactions` — Sample transaction data
  - `mock_etherscan_response` — Mock API responses
  - `eth_prices`, `btc_prices` — Mock price data

### 6. Example Scripts (examples/)
- ✅ **examples/basic_scan.py** — Basic whale scan example
- ✅ **examples/stream_alerts.py** — Real-time alert streaming
- ✅ **examples/agent_integration.py** — Agent integration with Simmer betting

### 7. CI/CD Pipeline
- ✅ **.github/workflows/ci.yml** — GitHub Actions CI
  - Test job: Python 3.11 and 3.12, pytest with coverage
  - Lint job: black, isort, mypy
  - Build job: Package build and validation
  - Coverage requirement: ≥ 90%

## Architectural Decisions

### 1. Agent-First Design
**Rationale:** Most crypto CLIs are designed for humans (pretty tables, parsed text). whalecli flips this: all output is JSON/JSONL by default, exit codes are meaningful, streaming is supported. Agents can call it programmatically without UI scraping.

### 2. SQLite for Local State
**Rationale:** Lightweight, no external dependencies, perfect for single-user local mode. Can migrate to PostgreSQL in v0.4 (Cloud mode) when multi-user support is needed.

### 3. Click for CLI Framework
**Rationale:** Python standard for CLIs, composable, excellent documentation. Easy to test with CliRunner.

### 4. Async Fetchers with httpx
**Rationale:** Async/await for concurrent API calls, connection pooling, better performance. httpx for HTTP/2 support and modern async API.

### 5. Whale Scoring Algorithm
**Rationale:** Multi-dimensional scoring captures more signal than raw flow amounts:
- Net flow score (weighted by wallet age)
- Velocity score (rate of change vs 30-day average)
- Correlation score (multiple whales moving together)
- Exchange flow indicator (CEX inflows/outflows)

### 6. JSONL for Streaming
**Rationale:** One JSON object per line, easy to parse line-by-line, no framing issues. Perfect for long-running processes and agent consumption.

### 7. Exit Codes Over Exceptions
**Rationale:** Agents depend on meaningful exit codes for conditional logic. Exit codes 0-4 map to specific error conditions (success, CLI error, API error, network error, data error).

### 8. Configuration: TOML + Env Vars
**Rationale:** TOML is human-readable and well-suited for config files. Env vars override for CI/CD and containerized deployments.

## Notes for Builder

### Implementation Order
1. **config.py** — Foundation, everything depends on config
2. **db.py** — State management, needed by all modules
3. **fetchers/** — Data sources (eth.py, btc.py, hl.py)
4. **scorer.py** — Core algorithm, uses fetchers + db
5. **cli.py** — Orchestration, calls all other modules
6. **alert.py** — Threshold detection, uses scorer
7. **stream.py** — Streaming, uses db + fetchers + scorer + alert
8. **output.py** — Formatting, used by all commands

### Key Implementation Details
- **Rate limiting:** Etherscan free tier is 5 calls/sec. Implement exponential backoff on 429 errors.
- **Caching:** Cache transactions for 24 hours (configurable) to avoid hitting rate limits.
- **Async:** All fetchers should be async for performance. Use asyncio in stream.py for polling.
- **Exit codes:** Every command must return meaningful exit codes (0-4).
- **JSON schemas:** All output must match the exact schemas defined in docs/API.md.
- **Type safety:** Full type annotations required. mypy should pass without errors.

### Testing Strategy
- **Unit tests:** Test each module in isolation with mocks.
- **Integration tests:** Test end-to-end CLI commands with CliRunner.
- **Coverage target:** ≥ 90% (enforced in CI)
- **Mock external APIs:** Use respx for httpx mocking.

### Quality Bar
- No shortcuts, no quick fixes. This is a ClawInfra repo.
- Documentation is already complete — Builder should focus on implementation.
- All TODOs in placeholder code must be implemented.
- Tests must be written alongside implementation (TDD).

## Files Created/Modified

**Total:** 26 files, 4,952 lines added

### Documentation (5 files)
- README.md
- docs/ARCHITECTURE.md
- docs/API.md
- docs/SKILL.md
- docs/ROADMAP.md
- docs/MODULES.md

### Code (16 files)
- pyproject.toml
- whalecli/__init__.py
- whalecli/cli.py
- whalecli/config.py
- whalecli/db.py
- whalecli/scorer.py
- whalecli/alert.py
- whalecli/stream.py
- whalecli/output.py
- whalecli/fetchers/__init__.py
- whalecli/fetchers/eth.py
- whalecli/fetchers/btc.py
- whalecli/fetchers/hl.py
- whalecli/skill/__init__.py
- whalecli/skill/whalecli_skill.py

### Tests (1 file)
- tests/conftest.py

### Examples (3 files)
- examples/basic_scan.py
- examples/stream_alerts.py
- examples/agent_integration.py

### CI/CD (1 file)
- .github/workflows/ci.yml

## Next Steps

The **Planner phase is complete**. The repo is ready for the **Builder phase**:

1. **Builder** should implement the placeholder modules in order (config → db → fetchers → scorer → cli → alert → stream → output)
2. **Write tests** alongside implementation (TDD)
3. **Maintain ≥ 90% coverage** (CI will enforce this)
4. **Follow ClawInfra standards:** Type-safe, test-driven, production-grade

## Quality Verification

✅ Every CLI command has 2+ example invocations with expected output
✅ JSON schemas are exact (field names, types, required/optional)
✅ Architecture diagram shows full data flow end-to-end
✅ No TODO placeholders — decided and documented rationale
✅ Docs complete enough for a senior engineer to implement without questions

---

**Planner:** whalecli-planner subagent
**Date:** 2026-02-22
**Status:** Complete ✅
