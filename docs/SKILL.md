# WhaleWatch CLI — OpenClaw Agent Skill Specification

This document defines `whalecli` as an OpenClaw agent skill. It covers when to use the skill, how to invoke the CLI, how to parse outputs, and how to integrate with the FearHarvester/Simmer closed loop.

---

## Overview

**Skill name:** `whalecli`  
**Type:** CLI skill (wraps `whalecli` command)  
**Purpose:** Provide real-time and historical whale wallet data to agents for reasoning and market signal generation  
**Output contract:** All outputs are JSON or JSONL; all exit codes are meaningful

---

## When to Use This Skill

The agent MUST invoke this skill when the user or system context includes any of the following:

### Trigger Phrases

**Direct invocations:**
- "What are the whales doing?"
- "Check whale activity"
- "Scan whale wallets"
- "Any whale moves on ETH/BTC?"
- "Check for large wallet movements"
- "Are whales accumulating or distributing?"
- "What's the on-chain signal?"
- "Run a whale scan"
- "Show me whale alerts"

**Market sentiment queries:**
- "What does on-chain data say?"
- "Should I go long/short based on whale activity?"
- "Is there smart money accumulating?"
- "Are exchanges seeing outflows?" (implies whale distribution check)

**Prediction market triggers (Simmer/Polymarket integration):**
- "Should I bet on ETH price going up/down?"
- "Check if there's a whale signal for [market]"
- "Run FearHarvester" (triggers the full closed-loop workflow)

### Automatic Triggers (no user prompt needed)

The agent SHOULD invoke this skill automatically:
- Every 60 minutes during market-active hours (configure via heartbeat)
- When a Simmer bet is being placed (pre-bet whale sanity check)
- When the fear/greed index crosses a threshold (corroboration)
- When asked for a market context report

---

## How the Agent Calls the CLI

The skill invokes `whalecli` via subprocess. Always use `--format json` or `--format jsonl` for machine-readable output.

### Basic Invocation Pattern

```python
import subprocess
import json

def run_whalecli(*args: str) -> dict:
    """Run whalecli with given args, return parsed JSON output."""
    result = subprocess.run(
        ["whalecli", *args],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if result.returncode == 2:
        error = json.loads(result.stderr)
        raise RuntimeError(f"whalecli error: {error['code']}: {error['message']}")
    
    if not result.stdout.strip():
        return {}  # No alerts (exit code 1)
    
    return json.loads(result.stdout)
```

### Standard Scan (most common)

```python
data = run_whalecli("scan", "--chain", "ETH", "--hours", "4", "--format", "json")
# Returns scan output schema (see docs/API.md)
```

### High-Priority Alert Check

```python
data = run_whalecli(
    "alert", "set", "--score", "80", "--window", "1h", "--format", "json"
)
if result.returncode == 0:
    # Alert triggered
    alerts = data["alerts"]
```

### Fleet Summary for Context Injection

```python
data = run_whalecli("report", "--summary", "--days", "7", "--format", "json")
# Use data as context for agent reasoning
```

### Streaming (async agent event loop)

```python
import asyncio
import json
import asyncio.subprocess

async def stream_whale_events(callback):
    proc = await asyncio.create_subprocess_exec(
        "whalecli", "stream", 
        "--chain", "ALL", 
        "--interval", "60", 
        "--format", "jsonl",
        stdout=asyncio.subprocess.PIPE
    )
    
    async for line in proc.stdout:
        event = json.loads(line.decode().strip())
        if event["type"] == "alert":
            await callback(event)
        elif event["type"] == "heartbeat":
            pass  # Normal, ignore
```

---

## How to Parse Outputs

### Step 1: Check Exit Code

```python
result = subprocess.run(["whalecli", "scan", "--format", "json"], ...)

if result.returncode == 0:
    # Alerts found — parse and act
    data = json.loads(result.stdout)
elif result.returncode == 1:
    # No alerts — note and continue
    data = None
elif result.returncode == 2:
    # Error — parse stderr for details
    error = json.loads(result.stderr)
    # Handle error based on error["code"]
```

### Step 2: Extract the Signal

```python
data = json.loads(result.stdout)

# Core signal fields
signal = data["summary"]["dominant_signal"]        # "accumulating" | "distributing" | "mixed" | "neutral"
net_flow = data["summary"]["total_net_flow_usd"]   # Positive = net accumulation

# Individual alerts
for alert in data["alerts"]:
    print(f"{alert['label']}: score={alert['score']}, direction={alert['direction']}")
    
    # High-conviction check
    if alert["score"] >= 85 and alert["score_breakdown"]["exchange_flow"] >= 70:
        print("HIGH CONVICTION: Exchange flow confirms signal")
```

### Step 3: Map to Market Direction

```python
def whale_signal_to_bet_direction(data: dict) -> str | None:
    """
    Map whale scan output to prediction market bet direction.
    Returns "LONG", "SHORT", or None (no bet, signal unclear).
    """
    signal = data["summary"]["dominant_signal"]
    net_flow = data["summary"]["total_net_flow_usd"]
    alerts_triggered = data["alerts_triggered"]
    
    # Require at least 2 alerts for signal validity
    if alerts_triggered < 2:
        return None
    
    # Strong accumulation = bullish = LONG
    if signal == "accumulation" and net_flow > 5_000_000:
        return "LONG"
    
    # Strong distribution = bearish = SHORT
    if signal == "distribution" and net_flow < -5_000_000:
        return "SHORT"
    
    return None  # Mixed or neutral signal
```

---

## Integration with FearHarvester/Simmer Loop

The complete closed loop: **on-chain signal → agent reasoning → prediction market bet**.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FearHarvester Loop                    │
│                                                         │
│  ┌──────────────┐                                       │
│  │  whalecli    │  ← on-chain signal                   │
│  │  stream/scan │                                       │
│  └──────┬───────┘                                       │
│         │ JSON signal                                   │
│  ┌──────▼───────┐                                       │
│  │  Agent       │  ← fear/greed index, news context    │
│  │  Reasoning   │                                       │
│  └──────┬───────┘                                       │
│         │ direction + confidence                        │
│  ┌──────▼───────┐                                       │
│  │  Simmer API  │  ← place prediction market bet       │
│  │  / Polymarket│                                       │
│  └──────┬───────┘                                       │
│         │ bet result                                    │
│  ┌──────▼───────┐                                       │
│  │  Outcome     │  ← track P/L, retrain score weights  │
│  │  Tracker     │                                       │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

### Implementation: FearHarvester Workflow

```python
import json
import subprocess
from typing import Optional

class FearHarvesterWorkflow:
    """
    Orchestrates the whale signal → agent reasoning → bet loop.
    """
    
    MIN_SCORE_FOR_BET = 80     # Only bet on high-confidence signals
    MIN_ALERTS_FOR_BET = 2     # Need corroboration from multiple wallets
    MIN_NET_FLOW_USD = 10_000_000  # $10M minimum net flow to act
    
    def run(self) -> Optional[dict]:
        """
        Run one iteration of the loop.
        Returns bet details if a bet was placed, None otherwise.
        """
        # Step 1: Get whale signal
        signal = self._get_whale_signal()
        if not signal:
            return None
        
        # Step 2: Get supplementary context
        fear_greed = self._get_fear_greed_index()
        
        # Step 3: Agent reasoning
        direction, confidence = self._reason(signal, fear_greed)
        if not direction:
            return None
        
        # Step 4: Place bet (if confidence high enough)
        if confidence >= 0.75:
            bet = self._place_simmer_bet(direction, confidence, signal)
            return bet
        
        return None
    
    def _get_whale_signal(self) -> Optional[dict]:
        """Run whalecli scan and return signal if alerts found."""
        result = subprocess.run(
            ["whalecli", "scan",
             "--chain", "ETH",
             "--hours", "4",
             "--threshold", str(self.MIN_SCORE_FOR_BET),
             "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            return None
        
        data = json.loads(result.stdout)
        
        # Validate signal quality
        if data["alerts_triggered"] < self.MIN_ALERTS_FOR_BET:
            return None
        
        if abs(data["summary"]["total_net_flow_usd"]) < self.MIN_NET_FLOW_USD:
            return None
        
        return data
    
    def _reason(self, signal: dict, fear_greed: dict) -> tuple[Optional[str], float]:
        """
        Multi-factor reasoning to determine trade direction and confidence.
        
        Returns: (direction, confidence)
          direction: "LONG" | "SHORT" | None
          confidence: 0.0–1.0
        """
        whale_signal = signal["summary"]["dominant_signal"]
        fg_value = fear_greed.get("value", 50)  # 0=extreme fear, 100=extreme greed
        
        # Contrarian + whale agreement logic:
        # Best bets: Whales accumulating during extreme fear = strong LONG
        # Whales distributing during extreme greed = strong SHORT
        
        confidence = 0.5  # Base
        direction = None
        
        if whale_signal == "accumulating":
            direction = "LONG"
            confidence += 0.20
            
            if fg_value < 25:  # Extreme fear — contrarian confirms
                confidence += 0.20
        
        elif whale_signal == "distributing":
            direction = "SHORT"
            confidence += 0.20
            
            if fg_value > 75:  # Extreme greed — contrarian confirms
                confidence += 0.20
        
        # Boost confidence if majority of wallets agree
        if signal["summary"]["accumulating"] >= 5 or signal["summary"]["distributing"] >= 5:
            confidence += 0.10
        
        # Cap at 0.95 (never 100% confident)
        confidence = min(0.95, confidence)
        
        if confidence < 0.70:
            direction = None  # Not confident enough
        
        return direction, confidence
    
    def _place_simmer_bet(self, direction: str, confidence: float, signal: dict) -> dict:
        """Place a bet on Simmer (or Polymarket) via their API."""
        # Implementation: call Simmer skill with bet details
        # This is a stub — see docs/SKILL.md for Simmer integration spec
        return {
            "direction": direction,
            "confidence": confidence,
            "whale_signal": signal["summary"]["dominant_signal"],
            "net_flow_usd": signal["summary"]["total_net_flow_usd"],
            "bet_placed": True
        }
```

### Streaming Trigger (Real-Time)

For continuous monitoring, use the stream command with a callback:

```python
async def fearharvester_stream_loop():
    """
    Run FearHarvester as a continuous stream.
    Bets when a high-score whale event arrives.
    """
    proc = await asyncio.create_subprocess_exec(
        "whalecli", "stream",
        "--chain", "ETH",
        "--interval", "60",
        "--threshold", "80",
        "--format", "jsonl",
        stdout=asyncio.subprocess.PIPE
    )
    
    async for raw_line in proc.stdout:
        event = json.loads(raw_line.decode().strip())
        
        if event["type"] != "alert":
            continue
        
        # Immediate high-confidence bet trigger
        if (event["score"] >= 90 and 
            event["score_breakdown"]["exchange_flow"] >= 75 and
            abs(event.get("net_flow_usd", 0)) >= 10_000_000):
            
            direction = "SHORT" if event["direction"] == "distributing" else "LONG"
            await place_simmer_bet(direction, confidence=0.85, trigger=event)
```

---

## Example Agent Workflows

### Workflow 1: Morning Whale Briefing

```
User: "What are the whales doing?"

Agent:
1. whalecli report --summary --days 1 --format json
   → Extract: dominant_signal, total_net_flow_usd, alerts_triggered

2. whalecli alert list --limit 5 --format json
   → Extract: recent alerts for context

3. Compose briefing:
   "In the last 24h, whale wallets show NET OUTFLOW of $120M (distribution signal).
    5 alerts triggered (3 warning, 2 info). Exchange inflows suggest selling pressure.
    Bearish implication for next 12-24h."
```

### Workflow 2: Pre-Bet Whale Sanity Check

```
Agent is about to place a LONG bet on ETH via Simmer.

Agent (automatic):
1. whalecli scan --chain ETH --hours 4 --threshold 70 --format json
   
   If exit code 1 (no alerts): proceed with bet, note "no strong whale signal"
   
   If exit code 0 + signal == "distribution":
      → ABORT bet (whales are distributing = counter-signal)
   
   If exit code 0 + signal == "accumulation":
      → STRENGTHEN bet position (whale confirmation)
```

### Workflow 3: Automated Alert Watch

```
EvoClaw cron job (every 30 min, 09:00–23:00):

1. whalecli alert set --score 75 --window 30m --format json
   
   exit code 1: HEARTBEAT_OK, no action needed
   
   exit code 0:
     → Parse signal direction
     → Notify Telegram: "🐋 Whale alert: {label} score={score} {signal}"
     → Log to daily memory file
     → Optional: trigger FearHarvester workflow if score >= 85
```

### Workflow 4: Wallet Fleet Management

```
User: "Add Binance's cold wallet and start tracking it"

Agent:
1. whalecli wallet add 0xF977814e90dA44bFA03b6295A0616a897441aceE \
     --chain ETH --label "Binance Cold 1"
   
2. whalecli scan --wallet 0xF977814e90dA44bFA03b6295A0616a897441aceE \
     --hours 24 --format json
   
3. Report: "Added Binance Cold 1. First scan: score 45, no alert. 
   Net flow last 24h: +$2.3M accumulation. Nothing alarming."
```

---

## OpenClaw Skill Registration

Register `whalecli` as an OpenClaw skill in `~/.evoclaw/agent.toml`:

```toml
[[skills]]
name = "whalecli"
type = "cli"
command = "whalecli"
description = """
Track whale wallet flows on ETH and BTC chains.
Returns scored alerts when large wallets make significant moves.
Use for: market signal generation, pre-bet validation, trend analysis.
Output: JSON by default, JSONL for streaming.
Key commands: scan, alert, stream, report, wallet.
"""
trigger_phrases = [
    "whale", "on-chain", "large wallet", "smart money",
    "accumulation", "distribution", "exchange flow"
]

# Example invocations shown to agent during skill selection
[[skills.examples]]
prompt = "What are whales doing on ETH?"
command = "whalecli scan --chain ETH --hours 4 --format json"

[[skills.examples]]
prompt = "Any whale alerts in the last hour?"
command = "whalecli alert set --score 75 --window 1h --format json"

[[skills.examples]]
prompt = "Show me the whale summary for the last week"
command = "whalecli report --summary --days 7 --format json"
```

---

## Output Parsing Cheat Sheet

| Goal | Command | Key fields |
|------|---------|-----------|
| Get market direction | `scan --hours 4` | `summary.dominant_signal`, `alerts_triggered` |
| Get flow magnitude | `scan --hours 24` | `summary.total_net_flow_usd` |
| Find top whale | `scan --all` | `alerts[0]` (sorted by score desc) |
| Check exchange pressure | `scan --chain ETH` | `alerts[].exchange_flow_fraction` |
| Get historical trend | `report --summary --days 7` | `fleet_summary.net_flow_usd`, `fleet_summary.dominant_signal` |
| Recent alerts | `alert list --limit 5` | `alerts[].triggered_at`, `alerts[].score` |

---

## Error Handling for Agents

```python
def safe_whale_scan(chain="ETH", hours=4) -> dict | None:
    """
    Safe wrapper: returns None on any error instead of raising.
    Agent should proceed without whale data if this returns None.
    """
    try:
        result = subprocess.run(
            ["whalecli", "scan",
             "--chain", chain,
             "--hours", str(hours),
             "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        log.warning("whalecli scan timed out, skipping whale check")
        return None
    except FileNotFoundError:
        log.error("whalecli not installed")
        return None
    
    if result.returncode == 1:
        return {"alerts": [], "summary": {"dominant_signal": "neutral"}}
    
    if result.returncode == 2:
        try:
            error = json.loads(result.stderr)
            log.error(f"whalecli error: {error['code']}: {error['message']}")
        except Exception:
            log.error(f"whalecli unknown error: {result.stderr}")
        return None
    
    return json.loads(result.stdout)
```
