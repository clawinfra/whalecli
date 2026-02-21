"""Agent integration example for whalecli.

This script demonstrates how an AI agent can integrate whalecli
for on-chain signal detection and prediction market betting.
"""

import subprocess
import json
from typing import Dict, Any


def scan_whales(chain: str = "ETH", hours: int = 24) -> Dict[str, Any]:
    """Scan whale wallets and return parsed results.

    This is a simple wrapper that agents can call.

    Args:
        chain: Blockchain to scan.
        hours: Time window in hours.

    Returns:
        Parsed scan results.

    Raises:
        RuntimeError: If scan fails.
    """
    result = subprocess.run(
        ["whalecli", "scan", "--chain", chain, "--hours", str(hours), "--format", "json"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"whalecli scan failed: {result.stderr}")

    return json.loads(result.stdout)


def place_bet_on_simmer(market: str, direction: str, amount: float):
    """Place a bet on Simmer prediction market.

    This is a placeholder for the actual Simmer API integration.

    Args:
        market: Market identifier (e.g., "ETH-USD").
        direction: "YES" or "NO".
        amount: Bet amount in USD.
    """
    # TODO: Implement actual Simmer API call
    print(f"[SIMMER] Placing {direction} bet on {market}: ${amount}")


def agent_loop():
    """Main agent loop: scan → reason → bet."""
    print("🤖 Agent started. Monitoring Ethereum whales...\n")

    while True:
        try:
            # 1. Scan for whale activity
            data = scan_whales(chain="ETH", hours=1)

            # 2. Filter for high-signal events
            high_signal = [w for w in data["wallets"] if w["score"] > 80]

            for whale in high_signal:
                # 3. Agent reasoning
                score = whale["score"]
                net_flow = whale["net_flow_usd"]
                direction = "YES" if net_flow > 0 else "NO"

                print(f"🐋 High-signal whale detected:")
                print(f"   Wallet: {whale['label'] or whale['address'][:10] + '...'}")
                print(f"   Score: {score}")
                print(f"   Flow: ${net_flow:,.0f}")

                # 4. Place bet if confidence is high
                if score > 85:
                    amount = min(100, abs(net_flow) / 100_000)  # Scale bet by flow
                    place_bet_on_simmer("ETH-USD", direction, amount)
                    print(f"   ✓ Bet placed: ${amount:.2f} on {direction}\n")

            # 5. Wait before next scan
            import time
            time.sleep(3600)  # 1 hour

        except KeyboardInterrupt:
            print("\n👋 Agent shutting down.")
            break
        except Exception as e:
            print(f"✗ Error: {e}")
            import time
            time.sleep(60)  # Wait 1 minute before retry


if __name__ == "__main__":
    agent_loop()
