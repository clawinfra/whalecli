"""JSONL streaming and continuous polling."""

import asyncio
import signal
import json
from typing import Iterator
from datetime import datetime
from whalecli.config import Config


class Streamer:
    """Manages continuous whale alert streaming."""

    def __init__(self, chain: str, interval: int, config: Config):
        """Initialize streamer.

        Args:
            chain: Blockchain to monitor.
            interval: Polling interval in seconds.
            config: Configuration object.
        """
        self.chain = chain
        self.interval = interval
        self.config = config
        self._running = False
        self._loop = None

    async def start(self):
        """Start streaming loop.

        Emits JSONL events to stdout.
        """
        # TODO: Implement in Builder phase
        self._running = True

        # Emit stream start event
        emit_event({
            "type": "stream_start",
            "timestamp": datetime.now().isoformat(),
            "chain": self.chain,
            "interval_seconds": self.interval
        })

        while self._running:
            try:
                # Poll for whale activity
                await self._poll()

                # Wait for next interval
                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue streaming
                emit_event({
                    "type": "error",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                })

        # Emit stream end event
        emit_event({
            "type": "stream_end",
            "timestamp": datetime.now().isoformat()
        })

    async def _poll(self):
        """Poll for whale activity.

        Emits poll_start, whale_alert, and poll_end events.
        """
        # TODO: Implement in Builder phase
        emit_event({
            "type": "poll_start",
            "timestamp": datetime.now().isoformat()
        })

        # Fetch transactions, calculate scores, check alerts
        # Placeholder: No alerts in this implementation

        emit_event({
            "type": "poll_end",
            "timestamp": datetime.now().isoformat(),
            "wallets_scanned": 0,
            "alerts": 0
        })

    def stop(self):
        """Stop streaming loop."""
        self._running = False


def emit_event(event: dict):
    """Emit a JSONL event to stdout.

    Args:
        event: Event data to emit.
    """
    # TODO: Implement in Builder phase
    print(json.dumps(event))


def handle_sigint(signum, frame):
    """Handle SIGINT for graceful shutdown.

    Args:
        signum: Signal number.
        frame: Current stack frame.
    """
    # TODO: Implement in Builder phase
    print("\nReceived SIGINT, shutting down gracefully...")
    # Signal the streamer to stop


def start_stream(chain: str, interval: int, config: Config):
    """Start streaming (sync wrapper for async start).

    Args:
        chain: Blockchain to monitor.
        interval: Polling interval in seconds.
        config: Configuration object.
    """
    # TODO: Implement in Builder phase
    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_sigint)

    # Create and start streamer
    streamer = Streamer(chain, interval, config)

    try:
        asyncio.run(streamer.start())
    except KeyboardInterrupt:
        streamer.stop()
