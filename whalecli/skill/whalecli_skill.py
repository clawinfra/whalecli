"""OpenClaw skill wrapper for whalecli CLI.

This module provides a Pythonic async API over the whalecli CLI,
designed for use as an OpenClaw agent skill.

Usage:
    skill = WhaleCliSkill()
    data = await skill.scan(chain="ETH", hours=4)

    async for event in skill.stream(chain="ETH", interval=60):
        if event["type"] == "alert":
            print(f"Alert: {event['label']} score={event['score']}")

See docs/SKILL.md for the full skill specification.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import AsyncIterator


class WhaleCliSkill:
    """
    OpenClaw skill wrapper for the whalecli CLI.

    Wraps subprocess calls to whalecli and provides typed async methods.
    All methods return parsed JSON dicts (not raw strings).

    Attributes:
        whalecli_path: Path or name of the whalecli executable.
    """

    def __init__(self, whalecli_path: str = "whalecli") -> None:
        self.whalecli_path = whalecli_path

    async def scan(
        self,
        chain: str = "ALL",
        hours: int = 24,
        threshold: int = 70,
        wallet: str | None = None,
    ) -> dict:
        """
        Run whalecli scan.

        Returns:
            Parsed scan output dict. Returns empty alerts list if exit code 1.

        Raises:
            RuntimeError: If whalecli returns exit code 2 (error).
        """
        args = [
            "scan",
            "--chain",
            chain,
            "--hours",
            str(hours),
            "--threshold",
            str(threshold),
            "--format",
            "json",
        ]
        if wallet:
            args.extend(["--wallet", wallet])

        code, stdout, stderr = await self._run(*args)

        if code == 2:
            self._raise_error(stderr)
        if code == 1 or not stdout.strip():
            return {"command": "scan", "alerts": [], "summary": {"dominant_signal": "neutral"}}
        return json.loads(stdout)

    async def report(
        self,
        summary: bool = True,
        days: int = 7,
        wallet: str | None = None,
    ) -> dict:
        """
        Run whalecli report.

        Returns:
            Parsed report output dict.
        """
        args = ["report", "--days", str(days), "--format", "json"]
        if summary:
            args.append("--summary")
        if wallet:
            args.extend(["--wallet", wallet])

        code, stdout, stderr = await self._run(*args)
        if code == 2:
            self._raise_error(stderr)
        return json.loads(stdout)

    async def alert_list(self, limit: int = 10) -> dict:
        """
        Run whalecli alert list.

        Returns:
            Parsed alert list output dict.
        """
        code, stdout, stderr = await self._run(
            "alert", "list", "--limit", str(limit), "--format", "json"
        )
        if code == 2:
            self._raise_error(stderr)
        return json.loads(stdout)

    async def stream(
        self,
        chain: str = "ALL",
        interval: int = 60,
        threshold: int = 70,
    ) -> AsyncIterator[dict]:
        """
        Stream whale events as an async generator.

        Yields parsed event dicts (alert, heartbeat, scan_complete).
        Stops when the subprocess ends (e.g., KeyboardInterrupt).

        Usage:
            async for event in skill.stream(chain="ETH"):
                if event["type"] == "alert":
                    handle_alert(event)
        """
        proc = await asyncio.create_subprocess_exec(
            self.whalecli_path,
            "stream",
            "--chain",
            chain,
            "--interval",
            str(interval),
            "--threshold",
            str(threshold),
            "--format",
            "jsonl",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        assert proc.stdout is not None  # noqa: S101

        async for raw_line in proc.stdout:
            line = raw_line.decode().strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue  # Skip malformed lines

    async def add_wallet(self, address: str, chain: str, label: str = "") -> dict:
        """
        Add a wallet to the tracking fleet.

        Returns:
            Success dict: {"success": True, "address": address, "chain": chain}

        Raises:
            RuntimeError: If wallet is invalid, duplicate, or error occurred.
        """
        args = ["wallet", "add", address, "--chain", chain]
        if label:
            args.extend(["--label", label])

        code, stdout, stderr = await self._run(*args)
        if code == 2:
            self._raise_error(stderr)
        return {"success": True, "address": address, "chain": chain, "label": label}

    async def _run(self, *args: str) -> tuple[int, str, str]:
        """
        Run whalecli with given arguments.

        Returns:
            (returncode, stdout, stderr) tuple.
        """
        proc = await asyncio.create_subprocess_exec(
            self.whalecli_path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode(),
            stderr.decode(),
        )

    def _raise_error(self, stderr: str) -> None:
        """Parse error JSON from stderr and raise RuntimeError."""
        try:
            error = json.loads(stderr)
            raise RuntimeError(
                f"whalecli error [{error.get('code', 'UNKNOWN')}]: {error.get('message', stderr)}"
            )
        except json.JSONDecodeError:
            raise RuntimeError(f"whalecli error: {stderr}")
