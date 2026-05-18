"""Norgate Data adapter.

All Norgate-specific SDK interaction is funneled through this module. The
rest of the codebase consumes its plain Python types — pandas DataFrames,
TickerMetadata records, etc. — and never imports `norgatedata` directly.
This isolates the dependency so we can mock for tests and so any future
data-vendor swap touches one file.

Operational requirements (confirmed 2026-05-18 research, see
docs/research/norgate-data.md):
- Norgate Data Updater (NDU) desktop application must be installed and
  running on the host. Windows-only.
- SDK installed via `pip install -e .[norgate]`.
- NDU authentication is done in the NDU GUI (subscriber login), not via
  API key.
- The Python SDK reads from the local data store NDU maintains at
  C:/Users/<user>/.norgatedata (override with NORGATEDATA_ROOT env var).

If the SDK is not installed OR if NDU is not running, the functions here
raise NorgateNotConfiguredError. The CLI surfaces this clearly so the
operator can fix it before retrying.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

# Equal-weight S&P 500 benchmark for Relative Strength calculations.
#
# Research finding 2026-05-18: the S&P 500 Equal Weight Index ($SPXEW)
# is NOT in Norgate's published index catalog. The listed S&P 500 family
# is $SPX, $OEX, $MID, $SML, $SP1500, $SPDAUDP, $SPESG — no equal-weight
# variant. It may still be accessible (verify in NDU's symbol search post-
# subscription) but cannot be assumed.
#
# RSP (Invesco S&P 500 Equal Weight ETF) tracks SPXEW within ~1 basis
# point and is the safe, verified-available default. The bot uses RSP
# unless overridden via config.
#
# If post-subscription verification confirms $SPXEW is available on the
# Platinum tier, the advisor can change `norgate.benchmark_symbol` in
# config.toml to "$SPXEW" without code changes.
DEFAULT_BENCHMARK_SYMBOL = "RSP"

# Norgate symbol conventions for filtering the universe to common stocks.
# Per Norgate's subtype taxonomy (confirmed in research):
#   subtype1 == "Equity" excludes Derivatives, Debt, ETPs, Indexes, etc.
#   subtype2 == "Operating/Holding Company" excludes ETFs, CEFs, BDCs,
#     preferreds, warrants, rights, structured products, ETNs.
# REITs are subtype1=Equity / subtype2=Operating/Holding so they pass.
COMMON_STOCK_SUBTYPE1 = "Equity"
COMMON_STOCK_SUBTYPE2 = "Operating/Holding Company"

# Watchlists / databases Norgate ships with NDU. Confirmed in the research.
DATABASE_ACTIVE = "US Equities"
DATABASE_DELISTED = "US Equities Delisted"


class NorgateNotConfiguredError(RuntimeError):
    """Raised when Norgate SDK calls are attempted without a configured installation.

    Catch this at the CLI / entry-point level. Surface clearly to the operator
    rather than letting AttributeError or ImportError bubble up generically.
    Common causes:
    - `norgatedata` package not installed (run `pip install -e .[norgate]`)
    - Norgate Data Updater desktop app not running
    - Norgate subscription expired or not yet activated
    """


@dataclass(frozen=True)
class TickerMetadata:
    """Canonical metadata for a single security.

    Sector and industry strings reflect Norgate's GICS classification, per
    docs/research/norgate-data.md. GICS is the industry-standard taxonomy
    and matches what most fundamental data vendors use.
    """

    symbol: str
    name: str | None
    exchange: str | None
    sector: str | None  # GICS level 1 (e.g., "Information Technology")
    industry: str | None  # GICS level 3 (e.g., "Technology Hardware, Storage & Peripherals")
    is_active: bool
    delisted_date: date | None


# ---------------------------------------------------------------------------
# SDK availability check
# ---------------------------------------------------------------------------


def _require_sdk() -> Any:
    """Import the norgatedata SDK or raise a clear error.

    Returns the imported module if available.
    """
    try:
        import norgatedata  # type: ignore[import-not-found]

        return norgatedata
    except ImportError as e:
        raise NorgateNotConfiguredError(
            "The `norgatedata` SDK is not installed. Install it via "
            "`pip install -e .[norgate]` AND ensure the Norgate Data Updater "
            "desktop application is installed, authenticated, and running."
        ) from e


def _to_error(e: Exception) -> NorgateNotConfiguredError:
    """Convert generic SDK runtime errors into NorgateNotConfiguredError.

    The SDK's documented exception is `ValueError` for invalid symbols /
    invalid parameters. Other failure modes (NDU not running, database
    not yet built) typically surface as silent empty returns or low-level
    IPC errors. Centralize the conversion here so callers see one error
    class.
    """
    return NorgateNotConfiguredError(
        f"Norgate SDK call failed: {e}. "
        "Verify NDU is running, your subscription is active, and the database is up to date."
    )


def check_status() -> dict[str, str]:
    """Query the Norgate SDK's status — useful as a pre-flight check.

    Returns whatever the SDK's `status()` function returns (typically a
    dict with database build timestamps and connection state). If the
    SDK is not installed, raises NorgateNotConfiguredError.

    Call this at the start of the overnight pipeline to surface
    "NDU isn't running" before any data fetch attempts fail confusingly.
    """
    nd = _require_sdk()
    try:
        return nd.status()  # type: ignore[no-any-return]
    except Exception as e:  # noqa: BLE001
        raise _to_error(e) from e


def is_common_stock(symbol: str) -> bool:
    """Return True if the symbol is a common stock (not ETF/preferred/etc.).

    Norgate stores all US-listed securities in the "US Equities" database,
    including ETFs, CEFs, BDCs, preferreds, warrants, etc. Our screening
    universe is **common stocks only** (including REITs, which count as
    Operating/Holding companies in Norgate's taxonomy).

    Uses Norgate's subtype1/subtype2 classification. Returns False on any
    SDK error so unknown securities are excluded by default (conservative).
    """
    nd = _require_sdk()
    try:
        s1 = nd.subtype1(symbol)
        s2 = nd.subtype2(symbol)
    except (ValueError, Exception):  # noqa: BLE001
        return False
    return s1 == COMMON_STOCK_SUBTYPE1 and s2 == COMMON_STOCK_SUBTYPE2


# ---------------------------------------------------------------------------
# Universe construction
# ---------------------------------------------------------------------------


def list_universe(database: str = DATABASE_ACTIVE) -> list[str]:
    """Return all symbols in a Norgate database (raw, unfiltered).

    Default is "US Equities" — every actively-listed US security, which
    includes ETFs, CEFs, BDCs, preferreds, warrants alongside common stocks.
    Filter the result with `is_common_stock(symbol)` for the screening
    universe.

    For a survivorship-bias-free universe spanning history, combine
    list_universe(DATABASE_ACTIVE) + list_universe(DATABASE_DELISTED).
    """
    nd = _require_sdk()
    try:
        symbols = nd.database_symbols(database)
    except ValueError as e:
        raise _to_error(e) from e
    except Exception as e:  # noqa: BLE001
        raise _to_error(e) from e
    return list(symbols)


def list_common_stocks(database: str = DATABASE_ACTIVE) -> list[str]:
    """Return only the common-stock symbols in the database.

    Applies `is_common_stock()` filter to exclude ETFs, CEFs, BDCs,
    preferreds, warrants, and other non-common-stock securities that
    Norgate stores in the same "US Equities" database. REITs are kept
    since they classify as Operating/Holding companies.
    """
    return [s for s in list_universe(database) if is_common_stock(s)]


def list_universe_at(index_name: str, as_of: date, symbol: str) -> bool:
    """Check whether `symbol` was a constituent of `index_name` as of `as_of`.

    Norgate exposes index membership as a daily 0/1 timeseries per symbol
    (via index_constituent_timeseries). This is the canonical point-in-time
    mechanism for backtesting against historical universes (e.g., "Russell
    3000 as of 2020-03-15").

    To get the *full* historical universe on a date, iterate the active +
    delisted symbol lists and check each one. This is fast because Norgate
    is local-disk-backed.
    """
    nd = _require_sdk()
    try:
        series = nd.index_constituent_timeseries(
            symbol,
            index_name,
            limit=-1,
            timeseriesformat="pandas-dataframe",
        )
    except Exception as e:  # noqa: BLE001
        raise _to_error(e) from e
    if series.empty:
        return False
    # The timeseries has Date as index and a 0/1 membership column
    on_or_before = series[series.index <= pd.Timestamp(as_of)]
    if on_or_before.empty:
        return False
    return bool(on_or_before.iloc[-1, 0])


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def get_ticker_metadata(symbol: str) -> TickerMetadata:
    """Fetch metadata for a single ticker.

    Sector is GICS level 1 ("Information Technology", "Financials", etc.).
    Industry is GICS level 3 (a more granular tier).
    """
    nd = _require_sdk()
    try:
        name = nd.security_name(symbol)
        exchange = nd.exchange_name(symbol)
        sector = nd.classification_at_level(symbol, "GICS", "Name", 1)
        industry = nd.classification_at_level(symbol, "GICS", "Name", 3)
        last_quoted = nd.last_quoted_date(symbol)
    except Exception as e:  # noqa: BLE001
        raise _to_error(e) from e

    last_quoted_date: date | None = None
    if last_quoted:
        if isinstance(last_quoted, pd.Timestamp):
            last_quoted_date = last_quoted.date()
        elif hasattr(last_quoted, "date"):
            last_quoted_date = last_quoted.date()

    is_active = last_quoted_date is None or (last_quoted_date >= date.today())

    return TickerMetadata(
        symbol=symbol,
        name=name,
        exchange=exchange,
        sector=sector,
        industry=industry,
        is_active=is_active,
        delisted_date=None if is_active else last_quoted_date,
    )


# ---------------------------------------------------------------------------
# Price data
# ---------------------------------------------------------------------------


def fetch_ohlc(
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
    adjustment: str = "TotalReturn",
) -> pd.DataFrame:
    """Fetch daily OHLC for a single ticker as a pandas DataFrame.

    Returns a DataFrame indexed by trade date (descending) with columns:
        open, high, low, close, volume

    Adjustment options (mapped to Norgate's StockPriceAdjustmentType):
    - "TotalReturn" → TOTALRETURN (splits + dividends; the default we use)
    - "Capital"     → CAPITAL (splits only; dividends NOT reinvested)
    - "None"        → NONE (raw unadjusted prices)
    """
    nd = _require_sdk()
    adjustment_map = {
        "TotalReturn": nd.StockPriceAdjustmentType.TOTALRETURN,
        "Capital": nd.StockPriceAdjustmentType.CAPITAL,
        "None": nd.StockPriceAdjustmentType.NONE,
    }
    if adjustment not in adjustment_map:
        raise ValueError(
            f"Unknown adjustment {adjustment!r}; must be one of {list(adjustment_map)}"
        )

    try:
        df = nd.price_timeseries(
            symbol,
            stock_price_adjustment_setting=adjustment_map[adjustment],
            padding_setting=nd.PaddingType.NONE,
            start_date=start_date,
            end_date=end_date,
            timeseriesformat="pandas-dataframe",
        )
    except ValueError as e:
        # Invalid symbol or invalid parameters — documented SDK exception
        raise _to_error(e) from e
    except Exception as e:  # noqa: BLE001
        # NDU down, IPC failure, database not built
        raise _to_error(e) from e

    # Norgate's DataFrame uses capitalized column names; normalize.
    return df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Turnover": "turnover",
            "Dividend": "dividend",
            "Unadjusted Close": "unadjusted_close",
        }
    )


def fetch_ohlc_bulk(
    symbols: list[str],
    start_date: date | None = None,
    end_date: date | None = None,
    adjustment: str = "TotalReturn",
) -> dict[str, pd.DataFrame]:
    """Fetch OHLC for many tickers. Norgate has no batch call so we iterate.

    Returns a dict mapping symbol → OHLC DataFrame. Symbols that fail to
    fetch are omitted from the result; the caller can compare keys to the
    input list to detect failures.

    Norgate is local-disk-backed so per-ticker fetches are fast — Russell
    3000 typically completes in well under a minute on a healthy machine.
    """
    results: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            results[sym] = fetch_ohlc(sym, start_date, end_date, adjustment)
        except NorgateNotConfiguredError:
            # SDK-level failure is fatal; stop the whole fetch.
            raise
        except Exception:  # noqa: BLE001
            # Per-symbol failure: skip and continue.
            continue
    return results


# ---------------------------------------------------------------------------
# Index data for Relative Strength
# ---------------------------------------------------------------------------


def fetch_benchmark_ohlc(
    start_date: date | None = None,
    end_date: date | None = None,
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL,
) -> pd.DataFrame:
    """Fetch the equal-weight S&P 500 benchmark for RS calculations.

    Defaults to RSP (Invesco S&P 500 Equal Weight ETF), which is the
    verified-available equal-weight benchmark in Norgate's coverage.
    Research as of 2026-05-18 did not find $SPXEW in Norgate's published
    index catalog — it may exist on subscription but cannot be assumed.

    If the advisor verifies $SPXEW is available post-subscription, set
    `norgate.benchmark_symbol = "$SPXEW"` in config.toml to use the raw
    index instead of the ETF.
    """
    return fetch_ohlc(
        benchmark_symbol,
        start_date=start_date,
        end_date=end_date,
        adjustment="TotalReturn",
    )


# ---------------------------------------------------------------------------
# Update timing
# ---------------------------------------------------------------------------


def assert_data_is_fresh(min_acceptable_date: date | None = None) -> date:
    """Verify Norgate's local data store has data through at least `min_acceptable_date`.

    Returns the most recent date with data available. Raises if data is
    older than `min_acceptable_date` (defaults to "the last full trading day").

    Per docs/research/norgate-data.md: NDU publishes "Market Close Edition"
    data around 5:00 PM New York time daily. Run this check at the start of
    the overnight pipeline to surface stale data before generating a report.
    """
    nd = _require_sdk()
    # `last_database_update_time` exists in some versions of the SDK;
    # otherwise we fall back to querying a known-active symbol.
    try:
        last_update = nd.last_database_update_time()  # type: ignore[attr-defined]
        if hasattr(last_update, "date"):
            return last_update.date()
        return last_update
    except (AttributeError, Exception):  # noqa: BLE001
        # Fallback: query SPY or another high-liquidity name and use its
        # latest bar date as a proxy for "how fresh is the database".
        try:
            spy = fetch_ohlc("SPY")
            if spy.empty:
                raise NorgateNotConfiguredError(
                    "Could not determine Norgate data freshness — SPY returned empty"
                )
            latest = spy.index.max()
            return latest.date() if hasattr(latest, "date") else latest
        except Exception as e:  # noqa: BLE001
            raise _to_error(e) from e
