"""Real-time whale alert streaming example.

This script demonstrates how to stream whale alerts in real-time.
"""

import subprocess
import json
import signal
import sys


def handle_sigint(signum, frame):
    """Handle SIGINT for graceful shutdown."""
    print("\nShutting down...")
    sys.exit(0)


def main():
    """Stream whale alerts from Ethereum."""
    signal.signal(signal.SIGINT, handle_sigint)

    print("Streaming Ethereum whale alerts (60s interval)...")
    print("Press Ctrl+C to stop.\n")

    process = subprocess.Popen(
        ["whalecli", "stream", "--chain", "ETH", "--interval", "60", "--format", "jsonl"],
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    for line in process.stdout:
        if not line.strip():
            continue

        event = json.loads(line)

        if event["type"] == "stream_start":
            print(f"✓ Stream started: {event['chain']}, interval {event['interval_seconds']}s")

        elif event["type"] == "poll_start":
            print(f"\n[{event['timestamp']}] Polling...")

        elif event["type"] == "whale_alert":
            wallet = event["wallet"]
            direction = event["direction"].upper()
            print(f"  🚨 WHALE ALERT: {wallet}")
            print(f"     Score: {event['score']}")
            print(f"     Flow: ${event['net_flow_usd']:,.0f} ({direction})")

        elif event["type"] == "poll_end":
            print(f"  ✓ Poll complete: {event['wallets_scanned']} wallets, {event['alerts']} alerts")

        elif event["type"] == "error":
            print(f"  ✗ Error: {event['error']}")


if __name__ == "__main__":
    main()
