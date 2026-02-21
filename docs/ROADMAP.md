# Roadmap — whalecli

Phased delivery plan for the whalecli project.

## v0.1 — Foundation (Current Phase)

**Goal:** MVP for tracking whale wallets on ETH and BTC chains with CLI and agent integration.

### Features
- ✅ CLI entry point with Click
- ✅ Wallet management (add/list/remove/import)
- ✅ Scan functionality (by chain, wallet, or all)
- ✅ Whale scoring algorithm (net flow, velocity, correlation)
- ✅ Alert system (threshold-based)
- ✅ JSON/JSONL/Table/CSV output formats
- ✅ SQLite database for local state
- ✅ Etherscan API integration (ETH)
- ✅ Mempool.space + Blockchain.info (BTC)
- ✅ Configuration management
- ✅ Complete documentation

### Deliverables
- [ ] Working CLI with all commands
- [ ] Test coverage ≥ 90%
- [ ] Documentation complete (README, ARCHITECTURE, API, SKILL)
- [ ] First release on PyPI

**Timeline:** 2 weeks

**Milestone Definition:** Agent can run `whalecli scan --chain ETH --hours 24 --format json` and get structured whale activity data.

---

## v0.2 — Real-Time & Prediction Market Integration

**Goal:** Close the loop from on-chain signal → agent reasoning → prediction market bet.

### Features
- WebSocket support for real-time whale alerts
- Hyperliquid perp flows integration
- FearHarvester sentiment integration
- Simmer/Polymarket betting integration
- Enhanced correlation analysis (multiple whales moving together)
- Webhook notifications (Telegram, Discord)
- Improved caching (Redis support)

### New Commands
```bash
whalecli stream --chain ETH --websocket  # Instead of polling
whalecli bet --auto --market ETH-USD     # Auto-bet on Simmer
whalecli sentiment --chain ETH           # Combine with FearHarvester
```

### Agent Workflow
```python
# Agent subscribes to WebSocket
ws = whalecli.subscribe(chain="ETH")

for alert in ws:
    if alert.score > 80:
        # Auto-bet on prediction market
        simmer.bet(market="ETH-USD", direction="YES", amount=100)
```

### Deliverables
- [ ] WebSocket server for real-time alerts
- [ ] Simmer/Polymarket client library
- [ ] FearHarvester integration tests
- [ ] Webhook notification system

**Timeline:** 3 weeks

**Milestone Definition:** Agent automatically places a prediction market bet when a whale score > 80 is detected.

---

## v0.3 — Advanced Analytics

**Goal:** ML-based anomaly detection and custom alert rules.

### Features
- Anomaly detection (isolation forest, LSTM)
- Custom alert rules DSL
- Backtesting engine
- Historical whale pattern analysis
- Multi-chain correlation (ETH ↔ BTC)
- Exchange flow tracking (CEX inflows/outflows)

### New Commands
```bash
whalecli analyze --anomaly --chain ETH
whalecli backtest --strategy custom --days 30
whalecli rules add "score > 80 AND net_flow > 10M"
```

### Alert Rules DSL
```python
# Custom alert rules
rule = """
  score > 80
  AND net_flow_usd > 10_000_000
  AND is_exchange_flow == true
  AND sentiment_score > 0.6
"""
whalecli rules add --name "strong_exchange_inflow" --rule "$rule"
```

### Deliverables
- [ ] Anomaly detection model (trained on historical data)
- [ ] DSL parser for custom rules
- [ ] Backtesting engine with performance metrics
- [ ] Exchange flow tracking

**Timeline:** 4 weeks

**Milestone Definition:** Agent can backtest a whale-based trading strategy and measure Sharpe ratio, max drawdown.

---

## v0.4 — Cloud Mode & Multi-User

**Goal:** Shared whale tracking database for multi-agent scenarios.

### Features
- PostgreSQL database backend
- Redis caching layer
- Multi-user support with ACLs
- REST API for remote access
- Docker deployment
- Kubernetes manifests

### Architecture Changes
```
┌─────────────────┐
│   REST API      │ (FastAPI)
└────────┬────────┘
         ▼
┌─────────────────┐
│   PostgreSQL    │ (Shared whale registry)
└────────┬────────┘
         ▼
┌─────────────────┐
│     Redis       │ (Transaction cache)
└─────────────────┘
```

### New Endpoints
```bash
POST /api/v1/wallets
GET  /api/v1/wallets
POST /api/v1/scan
GET  /api/v1/stream  # WebSocket
```

### Deliverables
- [ ] PostgreSQL schema migration
- [ ] Redis caching integration
- [ ] FastAPI REST API
- [ ] Docker Compose deployment
- [ ] Kubernetes Helm charts

**Timeline:** 3 weeks

**Milestone Definition:** Multiple agents can share a centralized whale tracking database via REST API.

---

## v0.5 — Full Multi-Chain Support

**Goal:** Add support for Solana, Polygon, Arbitrum, and other EVM chains.

### Features
- Solana whale tracking (RPC + Helius)
- Polygon whale tracking (PolygonScan)
- Arbitrum whale tracking (Arbiscan)
- Cross-chain arbitrage detection
- Unified scoring across chains

### New Commands
```bash
whalecli scan --chain SOL --hours 24
whalecli arbitrage --chains ETH,BTC,SOL
```

### Deliverables
- [ ] Solana fetcher (helius.io)
- [ ] Polygon/Arbitrum fetchers
- [ ] Cross-chain correlation analysis
- [ ] Arbitrage opportunity detector

**Timeline:** 4 weeks

**Milestone Definition:** Agent can detect arbitrage opportunities when whales move funds across chains.

---

## v1.0 — Production-Ready Platform

**Goal:** Enterprise-grade whale intelligence platform.

### Features
- Web dashboard (React)
- Mobile app (iOS/Android)
- Advanced analytics dashboard
- Custom whale labels and tags
- Team collaboration features
- Audit logging
- Rate limiting and quotas
- SSO integration (OAuth)

### Architecture
```
┌─────────────────┐
│  Web Dashboard  │ (React)
├─────────────────┤
│  Mobile Apps    │ (React Native)
├─────────────────┤
│   REST API      │ (FastAPI)
├─────────────────┤
│  WebSocket      │ (Real-time alerts)
├─────────────────┤
│   PostgreSQL    │
│     Redis       │
│   ClickHouse    │ (Analytics)
└─────────────────┘
```

### Deliverables
- [ ] Web dashboard (deployed on Vercel)
- [ ] Mobile apps (App Store + Play Store)
- [ ] ClickHouse analytics warehouse
- [ ] SSO integration
- [ ] Production deployment (AWS/GCP)

**Timeline:** 8 weeks

**Milestone Definition:** Non-technical users can track whales via web dashboard without using CLI.

---

## Future Enhancements (Post-v1.0)

### v1.1 — ML-Based Prediction
- Predict whale movements based on historical patterns
- Reinforcement learning for optimal bet sizing
- Natural language explanations for alerts

### v1.2 — Social Integration
- Track whale social media activity (Twitter, Discord)
- Correlate on-chain moves with off-chain signals
- Sentiment analysis from whale accounts

### v1.3 — DeFi Integration
- Track whale DeFi positions (Uniswap, Aave, Curve)
- Detect liquidation risks
- MEV protection alerts

### v2.0 — Autonomous Agent
- Fully autonomous whale tracking and betting agent
- Self-improving strategies via reinforcement learning
- Multi-agent coordination (swarm intelligence)

---

## Dependency Risks

### Etherscan Rate Limits
- **Risk:** Free tier limited to 5 calls/sec
- **Mitigation:** Aggressive caching, batch API calls, paid tier for production

### Prediction Market Liquidity
- **Risk:** Simmer/Polymarket may lack liquidity for某些 markets
- **Mitigation:** Limit bet sizes, diversify across markets

### API Key Security
- **Risk:** Exposing API keys in agent environments
- **Mitigation:** Env var override, encrypted config, rotating keys

### WebSocket Scalability
- **Risk:** Many agents subscribing to same WebSocket = high server load
- **Mitigation:** Redis pub/sub, horizontal scaling, load balancing

---

## Success Metrics

### v0.1 (MVP)
- [ ] 10+ whale wallets tracked
- [ ] 100+ scans completed successfully
- [ ] Test coverage ≥ 90%
- [ ] Documentation complete

### v0.2 (Real-Time)
- [ ] Sub-second alert latency
- [ ] 10+ auto-bets placed on Simmer
- [ ] Webhook delivery rate > 95%

### v0.3 (Analytics)
- [ ] Anomaly detection precision > 80%
- [ ] Backtesting engine supports 5+ strategies
- [ ] Custom rules DSL supports 10+ operators

### v0.4 (Cloud)
- [ ] 100+ concurrent API clients
- [ ] 99.9% uptime
- [ ] PostgreSQL query latency < 100ms

### v1.0 (Platform)
- [ ] 1000+ active users
- [ ] 10,000+ whale alerts sent
- [ ] 50+ prediction market bets placed
- [ ] Web dashboard DAU > 100

---

## Open Questions

### v0.1
- **Q:** Should we support Hyperliquid in v0.1 or defer to v0.2?
- **A:** Defer to v0.2 — focus on ETH/BTC first.

### v0.2
- **Q:** Which prediction market platform to prioritize — Simmer or Polymarket?
- **A:** Start with Simmer (simpler API), add Polymarket later.

### v0.3
- **Q:** Which ML model for anomaly detection?
- **A:** Isolation Forest (simple, interpretable) + LSTM (temporal patterns).

### v0.4
- **Q:** Self-hosted or managed PostgreSQL?
- **A:** Managed (RDS/Cloud SQL) for production, self-hosted for dev.

### v1.0
- **Q:** Web dashboard framework — React or Vue?
- **A:** React (larger ecosystem, easier hiring).

---

## Contributing

See `README.md` for contribution guidelines.

**Priority:** v0.1 (MVP) → v0.2 (Real-Time) → v0.3 (Analytics)

**Issue tracking:** https://github.com/clawinfra/whalecli/issues

**Project board:** https://github.com/clawinfra/whalecli/projects
