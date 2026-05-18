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

    Steps:
    1. Refresh universe metadata from Norgate
    2. Pull the latest OHLC bars (incremental)
    3. Run scoring over the universe (Section A pre-momentum + Section B in-momentum)
    4. Compile per-stock details and render HTML + PDF
    5. Send email to the advisor with the PDF attached
    6. Persist the report and delivery outcome to the audit log

    Errors at any step are logged and the audit row records the failure.
    """
    from datetime import date

    from pnf_bot.data import norgate, prices, storage as storage_mod, universe
    from pnf_bot.feedback import record_recommendation
    from pnf_bot.pnf import construct_chart, construct_rs_chart
    from pnf_bot.report import (
        SmtpConfig,
        compile_stock_detail,
        persist_report_to_audit_log,
        render_html_report,
        render_pdf_report,
        send_report_email,
    )
    from pnf_bot.scoring.composite import (
        build_daily_report,
        score_stock_in_momentum,
        score_stock_pre_momentum,
    )

    today = date.today()
    log.info("Daily run starting for %s", today)
    storage_mod.init_database(cfg.data.db_path)

    # Step 1+2: data refresh
    try:
        universe.refresh_universe(cfg)
        prices.refresh_latest_prices(cfg)
    except norgate.NorgateNotConfiguredError as e:
        log.error("Norgate not configured: %s", e)
        click.echo(f"ERROR: Norgate not configured: {e}", err=True)
        sys.exit(3)

    # Step 3: scoring
    log.info("Scoring universe")
    active_symbols = universe.get_active_universe(cfg)
    benchmark = None
    try:
        benchmark = norgate.fetch_benchmark_ohlc(benchmark_symbol=cfg.norgate.benchmark_symbol)
    except norgate.NorgateNotConfiguredError:
        log.warning("Benchmark fetch failed; running without RS data")

    candidates = []
    for sym in active_symbols:
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
        pre = score_stock_pre_momentum(sym, price_chart, rs_chart, as_of_date=today)
        if pre is not None:
            candidates.append((pre, price_chart, rs_chart))
        in_mom = score_stock_in_momentum(sym, price_chart, rs_chart, as_of_date=today)
        if in_mom is not None:
            candidates.append((in_mom, price_chart, rs_chart))

    report = build_daily_report(
        [c[0] for c in candidates],
        as_of_date=today,
        section_a_top_n=cfg.scoring.section_a_top_n,
        section_b_top_n=cfg.scoring.section_b_top_n,
    )
    log.info(
        "Built report: %d Section A, %d Section B, %d new last night",
        len(report.section_a_top_n),
        len(report.section_b_top_n),
        len(report.new_patterns_last_night),
    )

    # Step 4: compile details + render
    section_a_details = []
    for cand in report.section_a_top_n:
        for c, pc, rc in candidates:
            if c.symbol == cand.symbol and c.section == cand.section:
                section_a_details.append(compile_stock_detail(c, pc, rc))
                break
    section_b_details = []
    for cand in report.section_b_top_n:
        for c, pc, rc in candidates:
            if c.symbol == cand.symbol and c.section == cand.section:
                section_b_details.append(compile_stock_detail(c, pc, rc))
                break
    html = render_html_report(report, section_a_details, section_b_details)
    pdf_bytes = None
    try:
        pdf_bytes = render_pdf_report(report, section_a_details, section_b_details)
    except RuntimeError as e:
        log.warning("PDF rendering failed (WeasyPrint missing?): %s", e)

    # Step 5: deliver
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

    # Step 6: persist audit log
    persist_report_to_audit_log(
        db_path=cfg.data.db_path,
        report_date=today,
        recipient_email=cfg.report.recipient_email,
        subject_line=f"{cfg.report.subject_line} — {today}",
        html_content=html,
        pdf_bytes=pdf_bytes,
        archive_dir=cfg.report.archive_dir,
        parameter_snapshot={
            "section_a_top_n": cfg.scoring.section_a_top_n,
            "section_b_top_n": cfg.scoring.section_b_top_n,
            "benchmark_symbol": cfg.norgate.benchmark_symbol,
            "price_adjustment": cfg.norgate.price_adjustment,
            "min_price": cfg.data.min_price,
        },
        candidate_count_section_a=len(report.section_a_top_n),
        candidate_count_section_b=len(report.section_b_top_n),
        candidate_count_new_last_night=len(report.new_patterns_last_night),
        delivery_result=delivery_result,
    )

    # Step 7: feedback tracking
    for cand in report.section_a_top_n:
        record_recommendation(cfg.data.db_path, today, cand)
    for cand in report.section_b_top_n:
        record_recommendation(cfg.data.db_path, today, cand)

    log.info("Daily run complete")
    click.echo(f"Daily run complete. Section A: {len(report.section_a_top_n)}, "
               f"Section B: {len(report.section_b_top_n)}, "
               f"delivery: {'sent' if delivery_result.success else 'failed'}")


if __name__ == "__main__":
    main()
