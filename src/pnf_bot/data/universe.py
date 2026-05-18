"""Universe loader — assembles the daily list of tickers to evaluate.

Pulls from the Norgate adapter, applies the price floor, persists to storage.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from pnf_bot.config import Config
from pnf_bot.data import norgate, storage


def refresh_universe(config: Config) -> int:
    """Refresh the local Ticker table from Norgate's universe.

    Filters the raw "US Equities" database (which Norgate stuffs with ETFs,
    preferreds, BDCs, and other non-common-stock securities) down to
    common stocks only — Operating/Holding equity companies, including REITs.

    Returns the count of tickers in the active universe after refresh.

    Steps:
    1. Fetch the raw universe symbol list from Norgate
    2. Filter to common stocks via norgate.is_common_stock()
    3. For each remaining symbol, fetch metadata (name, exchange, sector)
    4. Upsert into the local Ticker table
    5. Mark delisted names is_active=False without deleting (audit trail)
    """
    common_stocks = norgate.list_common_stocks(config.norgate.universe_watchlist)

    with storage.get_session(config.data.db_path) as session:
        active_count = 0
        for symbol in common_stocks:
            try:
                meta = norgate.get_ticker_metadata(symbol)
            except norgate.NorgateNotConfiguredError:
                raise
            except Exception:  # noqa: BLE001
                # Per-ticker metadata fetch failure: skip, don't abort the whole refresh
                continue
            _upsert_ticker(session, meta)
            if meta.is_active:
                active_count += 1
        session.commit()
    return active_count


def get_active_universe(config: Config) -> list[str]:
    """Return the symbols currently in the active screening universe.

    Filters to is_active=True and price floor applied at the daily-bar
    level (not in this query — see filter_by_price_floor).
    """
    with storage.get_session(config.data.db_path) as session:
        results = (
            session.query(storage.Ticker.symbol)
            .filter(storage.Ticker.is_active.is_(True))
            .order_by(storage.Ticker.symbol)
            .all()
        )
    return [r[0] for r in results]


def filter_by_price_floor(
    config: Config,
    symbols: list[str],
    as_of: date | None = None,
) -> list[str]:
    """Apply the $1 minimum price floor from OQ-009.

    Excludes any symbol whose most recent close is below config.data.min_price.
    """
    floor = Decimal(str(config.data.min_price))
    with storage.get_session(config.data.db_path) as session:
        passing: list[str] = []
        for symbol in symbols:
            query = session.query(storage.DailyBar).filter(
                storage.DailyBar.symbol == symbol
            )
            if as_of is not None:
                query = query.filter(storage.DailyBar.trade_date <= as_of)
            latest = query.order_by(storage.DailyBar.trade_date.desc()).first()
            if latest is not None and latest.close >= floor:
                passing.append(symbol)
    return passing


def _upsert_ticker(session: Session, meta: norgate.TickerMetadata) -> None:
    """Insert or update a Ticker row from Norgate metadata."""
    existing = session.get(storage.Ticker, meta.symbol)
    if existing is None:
        session.add(
            storage.Ticker(
                symbol=meta.symbol,
                name=meta.name,
                exchange=meta.exchange,
                sector=meta.sector,
                industry=meta.industry,
                is_active=meta.is_active,
                delisted_date=meta.delisted_date,
            )
        )
    else:
        existing.name = meta.name
        existing.exchange = meta.exchange
        existing.sector = meta.sector
        existing.industry = meta.industry
        existing.is_active = meta.is_active
        existing.delisted_date = meta.delisted_date
        existing.last_updated = datetime.now(UTC)
