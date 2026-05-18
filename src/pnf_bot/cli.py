"""Command-line entry points for the PnF bot.

Commands:
    pnf-bot init-db                  — create or migrate the SQLite schema
    pnf-bot refresh-universe         — pull the latest universe membership from Norgate
    pnf-bot backfill-prices          — fetch historical OHLC for the active universe
    pnf-bot refresh-prices           — incremental daily price refresh
    pnf-bot daily-run                — full overnight pipeline (data + analysis + report)
    pnf-bot version                  — show the installed bot version

The daily-run command is what the Windows Task Scheduler / launchd job invokes.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from pnf_bot import __version__
from pnf_bot.config import load_config
from pnf_bot.data import storage, universe, prices

log = logging.getLogger("pnf_bot")


def _configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@click.group()
@click.option(
    "--config",
    "config_path",
    default="config.toml",
    type=click.Path(),
    help="Path to the TOML config file (default: config.toml in the working dir).",
)
@click.pass_context
def main(ctx: click.Context, config_path: str) -> None:
    """PnF Bot — daily Point & Figure stock screener."""
    cfg_path = Path(config_path)
    if not cfg_path.exists():
        click.echo(
            f"ERROR: Config file not found at {cfg_path.resolve()}.\n"
            "Copy config.toml.example to config.toml and fill in the values.",
            err=True,
        )
        sys.exit(2)
    cfg = load_config(cfg_path)
    _configure_logging(cfg.logging.log_level)
    ctx.obj = cfg


@main.command(name="version")
def version() -> None:
    """Print the installed bot version."""
    click.echo(f"pnf-bot {__version__}")


@main.command(name="init-db")
@click.pass_obj
def init_db(cfg) -> None:  # noqa: ANN001
    """Create the SQLite schema (idempotent)."""
    storage.init_database(cfg.data.db_path)
    click.echo(f"Database schema initialized at {cfg.data.db_path}")


@main.command(name="refresh-universe")
@click.pass_obj
def refresh_universe(cfg) -> None:  # noqa: ANN001
    """Refresh the universe of tickers from Norgate."""
    log.info("Refreshing universe from Norgate watchlist %s", cfg.norgate.universe_watchlist)
    count = universe.refresh_universe(cfg)
    click.echo(f"Active tickers in universe: {count}")


@main.command(name="backfill-prices")
@click.pass_obj
def backfill_prices(cfg) -> None:  # noqa: ANN001
    """Fetch historical OHLC for all active tickers."""
    log.info("Backfilling %d years of OHLC", cfg.data.backfill_years)
    inserted = prices.backfill_prices(cfg)
    click.echo(f"Inserted {inserted} historical bars.")


@main.command(name="refresh-prices")
@click.pass_obj
def refresh_prices(cfg) -> None:  # noqa: ANN001
    """Pull the most recent OHLC bars (incremental, daily)."""
    log.info("Refreshing recent OHLC")
    added = prices.refresh_latest_prices(cfg)
    click.echo(f"Added {added} new bars.")


@main.command(name="daily-run")
@click.pass_obj
def daily_run(cfg) -> None:  # noqa: ANN001
    """Full overnight pipeline — data refresh + analysis + report generation + email.

    PLACEHOLDER: phases 2-5 are not yet implemented. Today this command runs only
    the data layer (refresh universe + refresh prices). The analysis and reporting
    steps will be added incrementally as Phases 2, 4, and 5 land.
    """
    log.info("Daily run starting")
    storage.init_database(cfg.data.db_path)
    universe.refresh_universe(cfg)
    prices.refresh_latest_prices(cfg)
    # TODO(phase-2): compute P&F engine output for the universe
    # TODO(phase-4): apply pre-momentum and in-momentum scoring
    # TODO(phase-5): render and email the daily PDF report
    log.info("Daily run complete (data layer only — phases 2-5 pending)")
    click.echo("Daily run complete (data layer only — phases 2-5 pending implementation).")


if __name__ == "__main__":
    main()
