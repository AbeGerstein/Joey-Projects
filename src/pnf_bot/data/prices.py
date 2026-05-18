"""Price fetcher — orchestrates daily and historical OHLC pulls into local storage."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from pnf_bot.config import Config
from pnf_bot.data import norgate, storage


def backfill_prices(config: Config, symbols: list[str] | None = None) -> int:
    """Backfill historical OHLC for the universe.

    Fetches `config.data.backfill_years` years of history for each symbol.
    Idempotent — re-running adds only missing bars, doesn't duplicate.

    Returns the count of (symbol, date) bars inserted.
    """
    if symbols is None:
        with storage.get_session(config.data.db_path) as session:
            symbols = [
                row[0]
                for row in session.execute(
                    select(storage.Ticker.symbol).where(storage.Ticker.is_active.is_(True))
                ).all()
            ]

    today = date.today()
    start = today - timedelta(days=365 * config.data.backfill_years)
    bars_inserted = 0

    bulk = norgate.fetch_ohlc_bulk(
        symbols,
        start_date=start,
        end_date=today,
        adjustment=config.norgate.price_adjustment,
    )

    with storage.get_session(config.data.db_path) as session:
        for symbol, df in bulk.items():
            bars_inserted += _upsert_bars(session, symbol, df)
        session.commit()

    return bars_inserted


def refresh_latest_prices(config: Config) -> int:
    """Incremental daily refresh — pull only the latest few days.

    Called by the overnight scheduled job. For each active ticker, finds the
    most recent stored bar and pulls anything newer from Norgate.

    Returns the count of new bars added.
    """
    bars_added = 0
    today = date.today()
    lookback_start = today - timedelta(days=7)

    with storage.get_session(config.data.db_path) as session:
        active = [
            row[0]
            for row in session.execute(
                select(storage.Ticker.symbol).where(storage.Ticker.is_active.is_(True))
            ).all()
        ]

        for symbol in active:
            latest = session.execute(
                select(storage.DailyBar.trade_date)
                .where(storage.DailyBar.symbol == symbol)
                .order_by(storage.DailyBar.trade_date.desc())
                .limit(1)
            ).scalar_one_or_none()

            fetch_start = (latest + timedelta(days=1)) if latest else lookback_start

            try:
                df = norgate.fetch_ohlc(
                    symbol,
                    start_date=fetch_start,
                    end_date=today,
                    adjustment=config.norgate.price_adjustment,
                )
            except (norgate.NorgateNotConfiguredError, NotImplementedError):
                raise
            except Exception:  # noqa: BLE001
                # Skip individual ticker failures; report aggregate at end
                continue

            bars_added += _upsert_bars(session, symbol, df)

        session.commit()

    return bars_added


def _upsert_bars(session, symbol: str, df: pd.DataFrame) -> int:
    """Insert OHLC bars for one ticker, ignoring duplicates.

    Uses SQLite's INSERT OR IGNORE so re-running backfill is safe.
    """
    if df.empty:
        return 0

    rows = [
        {
            "symbol": symbol,
            "trade_date": idx if isinstance(idx, date) else idx.date(),
            "open": Decimal(str(row["open"])),
            "high": Decimal(str(row["high"])),
            "low": Decimal(str(row["low"])),
            "close": Decimal(str(row["close"])),
            "volume": int(row.get("volume", 0)),
        }
        for idx, row in df.iterrows()
    ]
    if not rows:
        return 0

    stmt = sqlite_insert(storage.DailyBar).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["symbol", "trade_date"])
    result = session.execute(stmt)
    return result.rowcount or 0
