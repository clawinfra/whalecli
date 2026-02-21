"""Basic whale scan example.

This script demonstrates how to use whalecli to scan for whale activity.
"""

import subprocess
import json


def main():
    """Run a basic whale scan on Ethereum."""
    print("Scanning Ethereum whales for the last 24 hours...")

    result = subprocess.run(
        ["whalecli", "scan", "--chain", "ETH", "--hours", "24", "--format", "json"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return

    data = json.loads(result.stdout)

    print(f"\nScan Results ({data['scan_time']}):")
    print(f"Wallets scanned: {data['wallets_scanned']}")
    print(f"Alerts triggered: {data['alerts_triggered']}")

    if data["wallets"]:
        print("\nTop Wallets:")
        for wallet in sorted(data["wallets"], key=lambda x: x["score"], reverse=True)[:5]:
            direction = "📈 INFLOW" if wallet["net_flow_usd"] > 0 else "📉 OUTFLOW"
            print(f"  • {wallet['label'] or wallet['address'][:10] + '...'}")
            print(f"    Score: {wallet['score']}")
            print(f"    {direction}: ${abs(wallet['net_flow_usd']):,.0f}")


if __name__ == "__main__":
    main()
