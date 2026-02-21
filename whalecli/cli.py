"""Click CLI entry point for whalecli.

All commands are thin orchestration wrappers — business logic lives in
config, db, fetchers, scorer, alert, output, and stream modules.

Exit codes:
  0 — success (or success with no whale alerts for scan/stream)
  1 — no results / no alerts found
  2 — API error, rate limit, invalid key
  3 — network error
  4 — data error (invalid address, wallet not found)
  5 — config error
  6 — database error
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from whalecli import __version__
from whalecli.config import (
    WhalecliConfig,
    get_default_config_path,
    load_config,
    save_config,
)
from whalecli.db import Database
from whalecli.exceptions import WhalecliError
from whalecli.output import format_output, mask_api_key

SUPPORTED_CHAINS = ["ETH", "BTC", "HL"]
SUPPORTED_CHAINS_ALL = SUPPORTED_CHAINS + ["ALL"]


# ── Error handler ─────────────────────────────────────────────────────────────


def _output_error(err: WhalecliError | Exception) -> None:
    """Write error JSON to stderr."""
    if isinstance(err, WhalecliError):
        payload = err.to_dict()
        exit_code = err.exit_code
    else:
        payload = {"error": "unknown_error", "message": str(err), "details": {}}
        exit_code = 1
    sys.stderr.write(json.dumps(payload) + "\n")
    sys.stderr.flush()
    sys.exit(exit_code)


def _db_from_config(config: WhalecliConfig) -> Database:
    """Create a Database instance from config."""
    db_path = config.database.path
    if db_path and db_path != ":memory:":
        db_path = str(Path(db_path).expanduser())
    return Database(db_path)


# ── Root group ────────────────────────────────────────────────────────────────


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    "config_path",
    envvar="WHALECLI_CONFIG",
    default=None,
    help="Config file path (default: ~/.whalecli/config.toml)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "jsonl", "table", "csv"]),
    default=None,
    help="Output format (overrides config default)",
)
@click.pass_context
def cli(ctx: click.Context, config_path: str | None, output_format: str | None) -> None:
    """WhaleWatch CLI — Agent-native whale wallet tracker."""
    ctx.ensure_object(dict)
    try:
        config = load_config(config_path)
    except WhalecliError as e:
        # On config errors, use defaults (so config init still works)
        from whalecli.config import WhalecliConfig

        config = WhalecliConfig()

    ctx.obj["config"] = config
    ctx.obj["format"] = output_format or config.output.default_format
    ctx.obj["config_path"] = config_path


# ── Wallet commands ───────────────────────────────────────────────────────────


@cli.group()
def wallet() -> None:
    """Manage tracked whale wallets."""


@wallet.command("add")
@click.argument("address")
@click.option("--chain", required=True, type=click.Choice(SUPPORTED_CHAINS), help="Chain")
@click.option("--label", default="", help="Human-readable label")
@click.option("--tag", "tags", multiple=True, help="Tags (repeatable)")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "table"]),
    default=None,
)
@click.pass_context
def wallet_add(
    ctx: click.Context,
    address: str,
    chain: str,
    label: str,
    tags: tuple[str, ...],
    fmt: str | None,
) -> None:
    """Add a whale wallet to the tracking fleet."""
    config: WhalecliConfig = ctx.obj["config"]
    fmt = fmt or ctx.obj.get("format", "json")

    async def _run() -> None:
        async with _db_from_config(config) as db:
            # Validate address
            fetcher = _get_fetcher_safe(chain, config)
            if fetcher and not await fetcher.validate_address(address):
                from whalecli.exceptions import InvalidAddressError

                raise InvalidAddressError(
                    f"Invalid {chain} address: {address!r}",
                    details={"address": address, "chain": chain},
                )

            wallet_data = await db.add_wallet(address, chain, label, list(tags))
            added_at = wallet_data.get("added_at", "")
            result = {
                "status": "added",
                "wallet": {
                    "address": wallet_data["address"],
                    "chain": wallet_data["chain"],
                    "label": wallet_data["label"],
                    "tags": wallet_data["tags"],
                    "added_at": added_at,
                    "active": True,
                },
            }
            click.echo(format_output(result, "json"))

    try:
        asyncio.run(_run())
    except WhalecliError as e:
        _output_error(e)


@wallet.command("list")
@click.option("--chain", type=click.Choice(SUPPORTED_CHAINS), default=None)
@click.option("--tag", "tags", multiple=True, help="Filter by tag")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "table", "csv"]),
    default=None,
)
@click.pass_context
def wallet_list(
    ctx: click.Context,
    chain: str | None,
    tags: tuple[str, ...],
    fmt: str | None,
) -> None:
    """List all tracked wallets."""
    config: WhalecliConfig = ctx.obj["config"]
    fmt = fmt or ctx.obj.get("format", "json")

    async def _run() -> None:
        async with _db_from_config(config) as db:
            wallets = await db.list_wallets(chain=chain, tags=list(tags) if tags else None)
            result = {
                "count": len(wallets),
                "wallets": wallets,
            }
            click.echo(format_output(result, fmt))

    try:
        asyncio.run(_run())
    except WhalecliError as e:
        _output_error(e)


@wallet.command("remove")
@click.argument("address")
@click.option("--chain", required=True, type=click.Choice(SUPPORTED_CHAINS))
@click.option("--purge", is_flag=True, help="Also delete cached transactions")
@click.pass_context
def wallet_remove(ctx: click.Context, address: str, chain: str, purge: bool) -> None:
    """Remove a tracked wallet (soft delete; keeps tx history unless --purge)."""
    config: WhalecliConfig = ctx.obj["config"]

    async def _run() -> None:
        async with _db_from_config(config) as db:
            result = await db.remove_wallet(address, chain, purge=purge)
            click.echo(format_output(result, "json"))

    try:
        asyncio.run(_run())
    except WhalecliError as e:
        _output_error(e)


@wallet.command("import")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True)
@click.pass_context
def wallet_import_cmd(ctx: click.Context, file_path: str, dry_run: bool) -> None:
    """Import wallets from a CSV file (address,chain,label,tags)."""
    config: WhalecliConfig = ctx.obj["config"]

    async def _run() -> None:
        rows = _parse_wallet_csv(file_path)
        async with _db_from_config(config) as db:
            result = await db.import_wallets(rows, dry_run=dry_run)
        click.echo(format_output(result, "json"))

    try:
        asyncio.run(_run())
    except (WhalecliError, ValueError) as e:
        (
            _output_error(e)
            if isinstance(e, WhalecliError)
            else (
                sys.stderr.write(json.dumps({"error": "cli_error", "message": str(e)}) + "\n")
                or sys.exit(1)
            )
        )


def _parse_wallet_csv(file_path: str) -> list[dict[str, Any]]:
    """Parse wallet CSV file. Returns list of row dicts."""
    rows = []
    with open(file_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


# ── Scan command ──────────────────────────────────────────────────────────────


@cli.command("scan")
@click.option("--chain", type=click.Choice(SUPPORTED_CHAINS_ALL), default=None)
@click.option("--wallet", "wallet_addr", default=None, help="Single wallet address")
@click.option("--all", "include_all", is_flag=True, help="Scan all tracked wallets")
@click.option("--hours", default=24, type=click.IntRange(1, 720), show_default=True)
@click.option("--threshold", default=0, type=click.IntRange(0, 100), show_default=True)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "jsonl", "table", "csv"]),
    default=None,
)
@click.option("--no-cache", is_flag=True)
@click.pass_context
def scan_command(
    ctx: click.Context,
    chain: str | None,
    wallet_addr: str | None,
    include_all: bool,
    hours: int,
    threshold: int,
    fmt: str | None,
    no_cache: bool,
) -> None:
    """Scan tracked wallets for whale activity."""
    config: WhalecliConfig = ctx.obj["config"]
    fmt = fmt or ctx.obj.get("format", "json")

    if not chain and not wallet_addr and not include_all:
        sys.stderr.write(
            json.dumps(
                {
                    "error": "cli_error",
                    "message": "Provide --chain, --wallet, or --all",
                }
            )
            + "\n"
        )
        sys.exit(1)

    async def _run() -> dict[str, Any]:
        from whalecli.alert import compute_scan_summary, process_alerts
        from whalecli.fetchers import get_fetcher
        from whalecli.scorer import load_exchange_addresses, score_wallet

        async with _db_from_config(config) as db:
            # Determine wallets to scan
            if wallet_addr:
                target_chain = (chain or "ETH").upper()
                try:
                    w = await db.get_wallet(wallet_addr, target_chain)
                    wallets = [w]
                except WhalecliError:
                    # Wallet not in DB — scan it ad-hoc
                    wallets = [
                        {
                            "address": wallet_addr,
                            "chain": target_chain,
                            "label": "",
                            "tags": [],
                        }
                    ]
            elif include_all or chain == "ALL" or not chain:
                query_chain = None if (include_all or chain == "ALL") else chain
                wallets = await db.list_wallets(chain=query_chain)
            else:
                wallets = await db.list_wallets(chain=chain.upper())

            if not wallets:
                from whalecli.exceptions import DataError

                raise DataError(
                    "No wallets tracked. Add wallets with `whalecli wallet add`.",
                    details={"chain": chain},
                )

            scan_time = datetime.now(tz=timezone.utc).isoformat()
            scan_id = f"scan_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

            # Score each wallet
            scored_wallets: list[dict[str, Any]] = []

            # Group by chain for efficient fetcher reuse
            chains_present = list({w["chain"] for w in wallets})
            wallet_txns: dict[str, list] = {}

            for wchain in chains_present:
                chain_wallets = [w for w in wallets if w["chain"] == wchain]
                try:
                    fetcher = get_fetcher(wchain, config)
                    exchange_addrs = load_exchange_addresses(wchain)
                except ValueError:
                    continue

                tasks = [_fetch_wallet_txns(w, hours, fetcher) for w in chain_wallets]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for w, txn_result in zip(chain_wallets, results):
                    txns: list[Any]
                    if isinstance(txn_result, (Exception, BaseException)):
                        txns = []
                    else:
                        txns = txn_result or []
                    wallet_txns[f"{w['address']}:{wchain}"] = txns

                # First pass: compute raw scores (without correlation)
                raw_scores: dict[str, dict] = {}
                for w in chain_wallets:
                    key = f"{w['address']}:{wchain}"
                    txns = wallet_txns.get(key, [])
                    hist = await db.get_score_history(w["address"], wchain, days=30)
                    avg_flow = sum(abs(h.get("net_flow_usd") or 0.0) for h in hist) / max(
                        len(hist), 1
                    )
                    scored = score_wallet(
                        address=w["address"],
                        chain=wchain,
                        transactions=txns,
                        wallet_age_days=0,
                        avg_30d_daily_flow_usd=avg_flow,
                        exchange_addresses=exchange_addrs,
                        all_wallet_directions={},
                        scan_hours=hours,
                        label=w.get("label", ""),
                    )
                    raw_scores[w["address"]] = scored

                # Build directions map for correlation pass
                directions_map = {
                    addr: s.get("direction", "neutral") for addr, s in raw_scores.items()
                }

                # Second pass: rescore with correlation
                for w in chain_wallets:
                    key = f"{w['address']}:{wchain}"
                    txns = wallet_txns.get(key, [])
                    hist = await db.get_score_history(w["address"], wchain, days=30)
                    avg_flow = sum(abs(h.get("net_flow_usd") or 0.0) for h in hist) / max(
                        len(hist), 1
                    )

                    # Peer directions = all other wallets in same chain
                    peer_directions = {
                        addr: d for addr, d in directions_map.items() if addr != w["address"]
                    }

                    scored = score_wallet(
                        address=w["address"],
                        chain=wchain,
                        transactions=txns,
                        wallet_age_days=0,
                        avg_30d_daily_flow_usd=avg_flow,
                        exchange_addresses=exchange_addrs,
                        all_wallet_directions=peer_directions,
                        scan_hours=hours,
                        label=w.get("label", ""),
                    )

                    # Apply score threshold filter
                    if threshold > 0 and scored["score"] < threshold:
                        scored_wallets.append(scored)
                        continue

                    # Persist score snapshot
                    await db.save_score(
                        {
                            "address": scored["address"],
                            "chain": scored["chain"],
                            "computed_at": scored["computed_at"],
                            "window_hours": hours,
                            "total": scored["score"],
                            "net_flow": scored["score_breakdown"]["net_flow"],
                            "velocity": scored["score_breakdown"]["velocity"],
                            "correlation": scored["score_breakdown"]["correlation"],
                            "exchange_flow": scored["score_breakdown"]["exchange_flow"],
                            "net_flow_usd": scored["net_flow_usd"],
                            "direction": scored["direction"],
                        }
                    )

                    scored_wallets.append(scored)

            # Process alerts
            alerts = await process_alerts(scored_wallets, db, config, scan_window_hours=hours)
            summary = compute_scan_summary(scored_wallets, alerts)

            # Build scan result
            visible_wallets = (
                [w for w in scored_wallets if w["score"] >= threshold]
                if threshold > 0
                else scored_wallets
            )

            return {
                "scan_id": scan_id,
                "scan_time": scan_time,
                "chain": chain or "all",
                "window_hours": hours,
                "wallets_scanned": len(wallets),
                "alerts_triggered": len(alerts),
                "wallets": visible_wallets,
                "summary": summary,
            }

    try:
        result = asyncio.run(_run())
        click.echo(format_output(result, fmt))
        if result.get("alerts_triggered", 0) > 0:
            sys.exit(0)
        else:
            sys.exit(0)  # Still success — no alerts isn't an error
    except WhalecliError as e:
        _output_error(e)


async def _fetch_wallet_txns(wallet: dict[str, Any], hours: int, fetcher: Any) -> list:
    """Fetch transactions for one wallet; return empty list on error."""
    try:
        return await fetcher.get_transactions(wallet["address"], hours)
    except Exception:
        return []


# ── Alert commands ────────────────────────────────────────────────────────────


@cli.group("alert")
def alert_group() -> None:
    """Configure and view whale alerts."""


@alert_group.command("set")
@click.option("--threshold", type=float, help="Alert on net_flow_usd exceeding this amount")
@click.option("--score", type=int, help="Alert on whale score >= this value (0–100)")
@click.option("--window", default="1h", help="Time window: 15m, 30m, 1h, 4h, 24h")
@click.option("--chain", type=click.Choice(SUPPORTED_CHAINS), default=None)
@click.option("--webhook", "webhook_url", default=None)
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default=None)
@click.pass_context
def alert_set(
    ctx: click.Context,
    threshold: float | None,
    score: int | None,
    window: str,
    chain: str | None,
    webhook_url: str | None,
    fmt: str | None,
) -> None:
    """Create an alert rule."""
    config: WhalecliConfig = ctx.obj["config"]
    fmt = fmt or ctx.obj.get("format", "json")

    if threshold is None and score is None:
        sys.stderr.write(
            json.dumps(
                {
                    "error": "cli_error",
                    "message": "Provide --threshold or --score",
                }
            )
            + "\n"
        )
        sys.exit(1)

    async def _run() -> None:
        async with _db_from_config(config) as db:
            rule_id = await db.get_next_rule_id()
            rule: dict[str, Any] = {
                "id": rule_id,
                "type": "score" if score is not None else "flow",
                "value": float(
                    score if score is not None else (threshold if threshold is not None else 0)
                ),
                "window": window,
                "chain": chain,
                "webhook_url": webhook_url,
                "created_at": datetime.now(tz=timezone.utc).isoformat(),
                "active": True,
            }
            await db.save_alert_rule(rule)
            result = {"status": "alert_configured", "rule": rule}
            click.echo(format_output(result, "json"))

    try:
        asyncio.run(_run())
    except WhalecliError as e:
        _output_error(e)


@alert_group.command("list")
@click.option("--limit", default=20, type=int)
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default=None)
@click.pass_context
def alert_list(ctx: click.Context, limit: int, fmt: str | None) -> None:
    """List alert rules and recent alert history."""
    config: WhalecliConfig = ctx.obj["config"]
    fmt = fmt or ctx.obj.get("format", "json")

    async def _run() -> None:
        async with _db_from_config(config) as db:
            rules = await db.list_alert_rules()
            recent = await db.list_alerts(limit=limit)
            result = {"rules": rules, "recent_alerts": recent}
            click.echo(format_output(result, fmt))

    try:
        asyncio.run(_run())
    except WhalecliError as e:
        _output_error(e)


# ── Stream command ────────────────────────────────────────────────────────────


@cli.command("stream")
@click.option("--chain", type=click.Choice(SUPPORTED_CHAINS_ALL), default="ALL")
@click.option("--interval", default=60, type=int, show_default=True)
@click.option("--threshold", default=70, type=click.IntRange(0, 100), show_default=True)
@click.option("--hours", default=1, type=int, show_default=True)
@click.option("--format", "fmt", type=click.Choice(["jsonl"]), default="jsonl")
@click.pass_context
def stream_command(
    ctx: click.Context,
    chain: str,
    interval: int,
    threshold: int,
    hours: int,
    fmt: str,
) -> None:
    """Stream real-time whale events as JSONL to stdout."""
    from whalecli.stream import run_stream

    config: WhalecliConfig = ctx.obj["config"]

    if chain == "ALL":
        chains = ["ETH", "BTC"]
    else:
        chains = [chain.upper()]

    async def _run() -> None:
        async with _db_from_config(config) as db:
            await run_stream(
                chains=chains,
                interval_seconds=interval,
                threshold=threshold,
                config=config,
                db=db,
                hours=hours,
            )

    try:
        asyncio.run(_run())
        sys.exit(130)  # stream ended (normal exit via SIGINT/cancel)
    except KeyboardInterrupt:
        sys.exit(130)
    except WhalecliError as e:
        _output_error(e)


# ── Report command ────────────────────────────────────────────────────────────


@cli.command("report")
@click.option("--wallet", "wallet_addr", default=None)
@click.option("--chain", type=click.Choice(SUPPORTED_CHAINS), default=None)
@click.option("--days", default=7, type=int, show_default=True)
@click.option("--summary", is_flag=True)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "table", "csv"]),
    default=None,
)
@click.pass_context
def report_command(
    ctx: click.Context,
    wallet_addr: str | None,
    chain: str | None,
    days: int,
    summary: bool,
    fmt: str | None,
) -> None:
    """Generate historical activity reports."""
    config: WhalecliConfig = ctx.obj["config"]
    fmt = fmt or ctx.obj.get("format", "json")

    if not wallet_addr and not summary:
        sys.stderr.write(
            json.dumps(
                {
                    "error": "cli_error",
                    "message": "Provide --wallet <address> or --summary",
                }
            )
            + "\n"
        )
        sys.exit(1)

    async def _run() -> dict[str, Any]:
        generated_at = datetime.now(tz=timezone.utc).isoformat()

        async with _db_from_config(config) as db:
            if summary:
                wallets = await db.list_wallets()
                report_rows = []
                agg_net = 0.0
                total_alerts = 0
                chain_counts: dict[str, int] = {}

                for w in wallets:
                    history = await db.get_score_history(w["address"], w["chain"], days=days)
                    net_flow = sum(h.get("net_flow_usd") or 0.0 for h in history)
                    peak_score = max((h.get("total_score", 0) for h in history), default=0)
                    alert_count = sum(1 for h in history if h.get("alert_triggered"))
                    direction = (
                        "accumulating"
                        if net_flow > 0
                        else "distributing" if net_flow < 0 else "neutral"
                    )
                    agg_net += net_flow
                    total_alerts += alert_count
                    chain_counts[w["chain"]] = chain_counts.get(w["chain"], 0) + 1

                    report_rows.append(
                        {
                            "address": w["address"],
                            "chain": w["chain"],
                            "label": w.get("label", ""),
                            "net_flow_usd": net_flow,
                            "peak_score": peak_score,
                            "alerts_triggered": alert_count,
                            "dominant_direction": direction,
                        }
                    )

                most_active = (
                    max(chain_counts, key=lambda c: chain_counts[c]) if chain_counts else None
                )
                agg_direction = (
                    "accumulating" if agg_net > 0 else "distributing" if agg_net < 0 else "neutral"
                )

                report_id = f"summary_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                return {
                    "report_id": report_id,
                    "generated_at": generated_at,
                    "period_days": days,
                    "total_wallets": len(wallets),
                    "wallets": report_rows,
                    "aggregate": {
                        "total_net_flow_usd": agg_net,
                        "dominant_direction": agg_direction,
                        "most_active_chain": most_active,
                        "total_alerts": total_alerts,
                    },
                }

            else:
                # Single wallet report
                assert wallet_addr is not None
                w = await db.get_wallet(wallet_addr, chain)
                history = await db.get_score_history(wallet_addr, w["chain"], days=days)

                net_flow = sum(h.get("net_flow_usd") or 0.0 for h in history)
                peak_score = max((h.get("total_score", 0) for h in history), default=0)
                avg_score = (
                    sum(h.get("total_score", 0) for h in history) // len(history) if history else 0
                )
                total_inflow = sum(max(h.get("net_flow_usd") or 0.0, 0) for h in history)
                total_outflow = abs(sum(min(h.get("net_flow_usd") or 0.0, 0) for h in history))
                total_alerts = sum(1 for h in history if h.get("alert_triggered"))
                tx_count = 0  # tx history not in scores table; approximate
                direction = (
                    "accumulating"
                    if net_flow > 0
                    else "distributing" if net_flow < 0 else "neutral"
                )

                # Daily breakdown from score history
                daily: list[dict[str, Any]] = []
                for h in sorted(history, key=lambda x: x.get("computed_at", "")):
                    comp_at = h.get("computed_at", "")
                    date_str = comp_at[:10] if comp_at else ""
                    nf = h.get("net_flow_usd") or 0.0
                    daily.append(
                        {
                            "date": date_str,
                            "inflow_usd": max(nf, 0.0),
                            "outflow_usd": abs(min(nf, 0.0)),
                            "net_flow_usd": nf,
                            "score": h.get("total_score", 0),
                            "tx_count": 0,
                        }
                    )

                report_id = f"report_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                return {
                    "report_id": report_id,
                    "generated_at": generated_at,
                    "period_days": days,
                    "wallet": {
                        "address": w["address"],
                        "chain": w["chain"],
                        "label": w.get("label", ""),
                    },
                    "summary": {
                        "total_inflow_usd": total_inflow,
                        "total_outflow_usd": total_outflow,
                        "net_flow_usd": net_flow,
                        "peak_score": peak_score,
                        "avg_score": avg_score,
                        "alerts_triggered": total_alerts,
                        "dominant_direction": direction,
                        "tx_count": tx_count,
                    },
                    "daily_breakdown": daily,
                    "top_counterparties": [],
                }

    try:
        result = asyncio.run(_run())
        click.echo(format_output(result, fmt))
    except WhalecliError as e:
        _output_error(e)


# ── Config commands ───────────────────────────────────────────────────────────


@cli.group("config")
def config_group() -> None:
    """Manage whalecli configuration."""


@config_group.command("init")
@click.option("--force", is_flag=True, help="Overwrite existing config")
@click.pass_context
def config_init(ctx: click.Context, force: bool) -> None:
    """Initialize default config at ~/.whalecli/config.toml."""
    provided = ctx.obj.get("config_path")
    config_path = Path(provided) if provided else get_default_config_path()

    if config_path.exists() and not force:
        click.echo(
            json.dumps(
                {
                    "status": "already_exists",
                    "config_path": str(config_path),
                    "hint": "Use --force to reinitialize",
                }
            )
        )
        return

    status = "initialized"
    backup = None

    if config_path.exists() and force:
        backup = str(config_path) + ".bak"
        import shutil

        shutil.copy2(config_path, backup)
        status = "reinitialized"

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = WhalecliConfig()
    save_config(config, str(config_path))

    result: dict[str, Any] = {
        "status": status,
        "config_path": str(config_path),
    }
    if backup:
        result["backup"] = backup
    click.echo(json.dumps(result))


@config_group.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set a config value by dotted key path (e.g. api.etherscan_api_key)."""
    config_path = ctx.obj.get("config_path")
    config: WhalecliConfig = ctx.obj["config"]

    parts = key.split(".", 1)
    if len(parts) != 2:
        sys.stderr.write(
            json.dumps(
                {
                    "error": "cli_error",
                    "message": f"Key must be in form section.key, got: {key!r}",
                }
            )
            + "\n"
        )
        sys.exit(1)

    section_name, field_name = parts
    section = getattr(config, section_name, None)
    if section is None:
        sys.stderr.write(
            json.dumps(
                {
                    "error": "config_invalid",
                    "message": f"Unknown config section: {section_name!r}",
                }
            )
            + "\n"
        )
        sys.exit(5)

    if not hasattr(section, field_name):
        sys.stderr.write(
            json.dumps(
                {
                    "error": "config_invalid",
                    "message": f"Unknown config key: {key!r}",
                }
            )
            + "\n"
        )
        sys.exit(5)

    # Type-coerce
    current = getattr(section, field_name)
    try:
        if isinstance(current, bool):
            typed_value: Any = value.lower() in ("1", "true", "yes")
        elif isinstance(current, int):
            typed_value = int(value)
        elif isinstance(current, float):
            typed_value = float(value)
        else:
            typed_value = value
        setattr(section, field_name, typed_value)
    except (ValueError, TypeError) as e:
        sys.stderr.write(json.dumps({"error": "config_invalid", "message": str(e)}) + "\n")
        sys.exit(5)

    save_config(config, config_path)

    # Mask API keys in response
    display_value = (
        mask_api_key(str(typed_value)) if "api_key" in field_name.lower() else typed_value
    )
    click.echo(json.dumps({"status": "updated", "key": key, "value": display_value}))


@config_group.command("show")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default=None)
@click.pass_context
def config_show(ctx: click.Context, fmt: str | None) -> None:
    """Show current configuration (API keys masked)."""
    config: WhalecliConfig = ctx.obj["config"]
    config_path = get_default_config_path()
    fmt = fmt or ctx.obj.get("format", "json")

    result = {
        "config_path": str(config_path),
        "api": {
            "etherscan_api_key": mask_api_key(config.api.etherscan_api_key),
            "blockchain_info_api_key": mask_api_key(config.api.blockchain_info_api_key),
            "hyperliquid_api_key": mask_api_key(config.api.hyperliquid_api_key),
        },
        "alert": {
            "score_threshold": config.alert.score_threshold,
            "flow_threshold_usd": config.alert.flow_threshold_usd,
            "window_minutes": config.alert.window_minutes,
            "webhook_url": config.alert.webhook_url,
        },
        "database": {
            "path": config.database.path,
            "cache_ttl_hours": config.database.cache_ttl_hours,
        },
        "output": {
            "default_format": config.output.default_format,
            "timezone": config.output.timezone,
            "color": config.output.color,
        },
        "cloud": {
            "enabled": config.cloud.enabled,
            "url": config.cloud.url,
        },
    }

    click.echo(format_output(result, "json"))


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_fetcher_safe(chain: str, config: WhalecliConfig) -> Any | None:
    """Return fetcher for chain, or None if unavailable."""
    try:
        from whalecli.fetchers import get_fetcher

        return get_fetcher(chain, config)
    except (ValueError, ImportError):
        return None


if __name__ == "__main__":
    cli()
