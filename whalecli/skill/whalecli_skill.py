"""OpenClaw agent skill for whalecli.

This module provides the agent-facing API for whalecli, allowing
EvoClaw, Claude, and other A2A participants to track whale wallets
programmatically.
"""

import subprocess
import json
from typing import Iterator, Dict, Any


def skill_init() -> bool:
    """Initialize the whalecli skill.

    Returns:
        True if initialization successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ["whalecli", "config", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def skill_scan(chain: str = "ETH", hours: int = 24, wallet: str | None = None) -> Dict[str, Any]:
    """Scan whale wallets for activity.

    Args:
        chain: Blockchain to scan (ETH, BTC, HL)
        hours: Time window in hours
        wallet: Optional specific wallet address to scan

    Returns:
        Scan results as a dictionary.

    Raises:
        RuntimeError: If whalecli is not installed or scan fails.
    """
    cmd = ["whalecli", "scan", "--chain", chain, "--hours", str(hours), "--format", "json"]

    if wallet:
        cmd.extend(["--wallet", wallet])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        raise RuntimeError(f"whalecli scan failed (exit {result.returncode}): {result.stderr}")

    return json.loads(result.stdout)


def skill_stream(chain: str = "ETH", interval: int = 60) -> Iterator[Dict[str, Any]]:
    """Stream whale alerts in real-time.

    Args:
        chain: Blockchain to monitor (ETH, BTC, HL)
        interval: Polling interval in seconds

    Yields:
        Alert events as dictionaries.

    Raises:
        RuntimeError: If whalecli is not installed or stream fails.
    """
    cmd = ["whalecli", "stream", "--chain", chain, "--interval", str(interval), "--format", "jsonl"]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1  # Line buffered
    )

    try:
        for line in process.stdout:
            if line.strip():
                yield json.loads(line)
    finally:
        process.terminate()
        process.wait(timeout=5)
