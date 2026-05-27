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
from pnf_bot.data import prices, storage, universe

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
    # Skip config loading if the user is just asking for help OR running version.
    # This makes the CLI surface inspectable without needing a valid config first.
    if "--help" in sys.argv or "-h" in sys.argv or "version" in sys.argv[1:]:
        ctx.obj = None
        return

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
    """Full overnight pipeline using the checklist methodology.

    Steps:
    1. Refresh universe metadata + latest prices from Norgate.
    2. Build per-stock state (charts, latest signals, TA composite).
    3. Compute YESTERDAY's TA per stock (chart with one less bar).
    4. Aggregate sector indicators (BP/RSX/RSP/PT → Favored/Average/Unfavored).
    5. Rank stocks within each sector.
    6. Run the checklist ranker → List 1 (fired today) + List 2 (one box away).
    7. Render HTML/PDF.
    8. Send email and persist the audit log.

    Errors at any step are logged; the audit row records the outcome.
    """
    from datetime import date

    from sqlalchemy import select

    from pnf_bot.data import norgate, prices, universe
    from pnf_bot.data import storage as storage_mod
    from pnf_bot.pnf import construct_chart, construct_rs_chart
    from pnf_bot.pnf.signals import latest_signal
    from pnf_bot.pnf.trendlines import is_above_bullish_support
    from pnf_bot.report import (
        SmtpConfig,
        persist_report_to_audit_log,
        render_checklist_html,
        render_checklist_pdf,
        send_report_email,
    )
    from pnf_bot.scoring.checklist import run_checklist
    from pnf_bot.scoring.intra_sector_rank import rank_within_sectors
    from pnf_bot.scoring.sector_indicators import classify_all_sectors
    from pnf_bot.scoring.stock_state import StockState
    from pnf_bot.scoring.ta_composite import compute_ta_equivalent

    today = date.today()
    log.info("Daily run starting for %s (checklist methodology)", today)
    storage_mod.init_database(cfg.data.db_path)

    # 1. Refresh data
    try:
        universe.refresh_universe(cfg)
        prices.refresh_latest_prices(cfg)
    except norgate.NorgateNotConfiguredError as e:
        log.error("Norgate not configured: %s", e)
        click.echo(f"ERROR: Norgate not configured: {e}", err=True)
        sys.exit(3)

    # Benchmark for RS charts + Rrisk
    benchmark = None
    try:
        benchmark = norgate.fetch_benchmark_ohlc(benchmark_symbol=cfg.norgate.benchmark_symbol)
    except norgate.NorgateNotConfiguredError:
        log.warning("Benchmark fetch failed; W1 RS-buy proximity will be off")

    # Active universe with sector info
    with storage_mod.get_session(cfg.data.db_path) as session:
        ticker_rows = session.execute(
            select(storage_mod.Ticker.symbol, storage_mod.Ticker.sector)
            .where(storage_mod.Ticker.is_active.is_(True))
        ).all()
    symbol_to_sector: dict[str, str | None] = dict(ticker_rows)
    log.info("Building per-stock state for %d active tickers", len(symbol_to_sector))

    stock_states: list[StockState] = []
    raw_ohlc_by_symbol = {}
    yesterday_ta_scores: dict[str, int] = {}
    as_of_date = today

    for sym, sector in symbol_to_sector.items():
        try:
            ohlc = norgate.fetch_ohlc(sym, adjustment=cfg.norgate.price_adjustment)
        except Exception:  # noqa: BLE001
            continue
        if ohlc.empty or len(ohlc) < 20:
            continue

        try:
            price_chart = construct_chart(sym, ohlc)
            rs_chart = (
                construct_rs_chart(sym, ohlc, benchmark) if benchmark is not None else None
            )
        except Exception:  # noqa: BLE001
            continue

        ta = compute_ta_equivalent(price_chart, rs_chart=rs_chart)

        # Yesterday's TA: drop the last bar and recompute
        if len(ohlc) >= 21:
            try:
                ohlc_yesterday = ohlc.iloc[:-1]
                bench_yesterday = (
                    benchmark.iloc[:-1] if benchmark is not None and len(benchmark) >= 2 else None
                )
                yesterday_chart = construct_chart(sym, ohlc_yesterday)
                yesterday_rs = (
                    construct_rs_chart(sym, ohlc_yesterday, bench_yesterday)
                    if bench_yesterday is not None
                    else None
                )
                ta_y = compute_ta_equivalent(yesterday_chart, rs_chart=yesterday_rs)
                yesterday_ta_scores[sym] = ta_y.score
            except Exception:  # noqa: BLE001
                pass

        # Use the latest bar's date as the "as_of_date" for the checklist —
        # signals' fired_date will compare against this, so it must match the
        # chart's actual latest column end_date (which can lag today's calendar
        # date if markets were closed).
        as_of_date = ohlc.index[-1].date()

        stock_states.append(
            StockState(
                symbol=sym,
                sector=sector,
                price_chart=price_chart,
                rs_chart_vs_market=rs_chart,
                latest_price_signal=latest_signal(price_chart),
                latest_rs_vs_market_signal=(
                    latest_signal(rs_chart) if rs_chart is not None else None
                ),
                ta_score=ta.score,
                above_bullish_support=is_above_bullish_support(price_chart),
            )
        )
        raw_ohlc_by_symbol[sym] = ohlc

    log.info(
        "Built %d stock states; yesterday TA known for %d; as_of_date=%s",
        len(stock_states),
        len(yesterday_ta_scores),
        as_of_date,
    )

    # 4-5. Sector aggregation + intra-sector ranking
    sector_indicators = classify_all_sectors(stock_states)
    intra_sector_ranks = rank_within_sectors(stock_states)
    favored_count = sum(1 for s in sector_indicators.values() if s.classification == "favored")
    log.info(
        "Sector classification: %d favored / %d total",
        favored_count, len(sector_indicators),
    )

    # 6. Run checklist
    report = run_checklist(
        stocks=stock_states,
        raw_ohlc_by_symbol=raw_ohlc_by_symbol,
        benchmark_ohlc=benchmark,
        sector_indicators=sector_indicators,
        intra_sector_ranks=intra_sector_ranks,
        yesterday_ta_scores=yesterday_ta_scores,
        as_of_date=as_of_date,
        top_n=30,
    )
    log.info(
        "Checklist built: List 1 (fired today) = %d, List 2 (one box away) = %d, OBOS-eliminated = %d",
        len(report.list_1_fired_today),
        len(report.list_2_one_box_away),
        report.eliminated_obos_count,
    )

    # 7. Render
    html = render_checklist_html(report)
    pdf_bytes = None
    try:
        pdf_bytes = render_checklist_pdf(report)
    except RuntimeError as e:
        log.warning("PDF rendering failed (WeasyPrint missing?): %s", e)

    # 8. Send + persist
    smtp = SmtpConfig(
        host=cfg.email.smtp_host,
        port=cfg.email.smtp_port,
        username=cfg.email.smtp_user,
        password=cfg.email.smtp_password,
        from_address=cfg.email.smtp_from,
        use_tls=cfg.email.smtp_use_tls,
    )
    delivery_result = send_report_email(
        smtp_config=smtp,
        recipient_email=cfg.report.recipient_email,
        subject_line=f"{cfg.report.subject_line} — {today}",
        html_body=html,
        pdf_bytes=pdf_bytes,
    )
    if delivery_result.success:
        log.info("Email delivered to %s", delivery_result.recipient)
    else:
        log.error("Email delivery failed: %s", delivery_result.error_message)

    persist_report_to_audit_log(
        db_path=cfg.data.db_path,
        report_date=today,
        recipient_email=cfg.report.recipient_email,
        subject_line=f"{cfg.report.subject_line} — {today}",
        html_content=html,
        pdf_bytes=pdf_bytes,
        archive_dir=cfg.report.archive_dir,
        parameter_snapshot={
            "methodology": "checklist_v1",
            "top_n": 30,
            "benchmark_symbol": cfg.norgate.benchmark_symbol,
            "price_adjustment": cfg.norgate.price_adjustment,
            "min_price": cfg.data.min_price,
        },
        # Reuse the audit-log fields for the new methodology:
        # section_a → List 1 (fired today)
        # section_b → List 2 (one box away)
        # new_last_night → OBOS-eliminated count (informational)
        candidate_count_section_a=len(report.list_1_fired_today),
        candidate_count_section_b=len(report.list_2_one_box_away),
        candidate_count_new_last_night=report.eliminated_obos_count,
        delivery_result=delivery_result,
    )

    click.echo(
        f"Daily run complete. List 1: {len(report.list_1_fired_today)}, "
        f"List 2: {len(report.list_2_one_box_away)}, "
        f"delivery: {'sent' if delivery_result.success else 'failed'}"
    )
    log.info("Daily run complete")
    click.echo(f"Daily run complete. Section A: {len(report.section_a_top_n)}, "
               f"Section B: {len(report.section_b_top_n)}, "
               f"delivery: {'sent' if delivery_result.success else 'failed'}")


if __name__ == "__main__":
    main()
