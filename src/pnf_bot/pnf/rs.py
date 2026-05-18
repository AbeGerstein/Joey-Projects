"""Relative Strength chart construction and regime detection.

Per DWA's documented methodology:
- RS ratio = (security price / benchmark price) × 100
- Benchmark is the S&P 500 Equal Weight Index (Norgate symbol $SPXEW)
  or its ETF proxy RSP. See docs/methodology/relative-strength.md.
- The RS ratio is plotted as a P&F chart with **percentage scaling**:
    - 6.5% boxes for stock RS
    - 3.25% boxes for fund RS
- Reversal: 3 boxes (project default)

This module exposes:
- `construct_rs_chart(symbol, security_ohlc, benchmark_ohlc, ...)` — builds the chart
- `rs_signal_status(rs_chart)` — current RS regime (buy / sell / none)
- `is_rs_positive_trend(rs_chart)` — RS above its own bullish support line

The RS chart is just another PnFChart, so signal detection and trendline
analysis work identically — pass it to `detect_signals()` or
`find_bullish_support_line()` as usual.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

import pandas as pd

from pnf_bot.pnf.box_scaling import PercentageScaling
from pnf_bot.pnf.chart import construct_chart
from pnf_bot.pnf.signals import latest_signal
from pnf_bot.pnf.trendlines import is_above_bullish_support, is_below_bearish_resistance
from pnf_bot.pnf.types import PnFChart

# Standard DWA box sizes for RS charts
STOCK_RS_BOX_PCT = Decimal("0.065")
FUND_RS_BOX_PCT = Decimal("0.0325")

RSSignalStatus = Literal["buy", "sell", "none"]


def compute_rs_ohlc(
    security_ohlc: pd.DataFrame,
    benchmark_ohlc: pd.DataFrame,
) -> pd.DataFrame:
    """Compute the RS ratio time series as an OHLC-shaped DataFrame.

    Returns a DataFrame indexed by date with `high` and `low` columns
    representing the daily RS ratio range.

    The ratio's intraday range is estimated using:
        high = security.high / benchmark.low × 100
        low  = security.low  / benchmark.high × 100
    This gives the security's max possible outperformance/underperformance
    for the day, anchoring the P&F chart's high/low logic to a wider
    intraday range than a closing-only ratio would.

    Rows where either security or benchmark data is missing are dropped.
    """
    merged = security_ohlc.join(
        benchmark_ohlc,
        lsuffix="_sec",
        rsuffix="_bench",
        how="inner",
    ).dropna(subset=["high_sec", "low_sec", "high_bench", "low_bench"])

    rs = pd.DataFrame(index=merged.index)
    rs["high"] = merged["high_sec"] / merged["low_bench"] * 100
    rs["low"] = merged["low_sec"] / merged["high_bench"] * 100
    return rs


def construct_rs_chart(
    symbol: str,
    security_ohlc: pd.DataFrame,
    benchmark_ohlc: pd.DataFrame,
    box_pct: Decimal = STOCK_RS_BOX_PCT,
    reversal_boxes: int = 3,
) -> PnFChart:
    """Build the Relative Strength P&F chart for a security vs a benchmark.

    Uses percentage scaling per DWA convention. Defaults to 6.5% boxes
    (the stock RS convention); pass `FUND_RS_BOX_PCT` (3.25%) for funds.

    The returned PnFChart's columns reflect the RS ratio's path over time.
    Standard signal detection and trendline functions work on it directly.
    """
    rs_ohlc = compute_rs_ohlc(security_ohlc, benchmark_ohlc)
    scaling = PercentageScaling(box_pct)
    return construct_chart(
        symbol=f"{symbol}_RS",
        ohlc=rs_ohlc,
        scaling=scaling,
        reversal_boxes=reversal_boxes,
    )


# ---------------------------------------------------------------------------
# Regime detection accessors
# ---------------------------------------------------------------------------


def rs_signal_status(rs_chart: PnFChart) -> RSSignalStatus:
    """Return the chart's current RS signal posture.

    - "buy"  — most recent signal in the chart is bullish (DT, TT, etc.)
    - "sell" — most recent signal is bearish (DB, TB, etc.)
    - "none" — no signal has fired yet
    """
    sig = latest_signal(rs_chart)
    if sig is None:
        return "none"
    return "buy" if sig.is_bullish else "sell"


def is_rs_positive_trend(rs_chart: PnFChart) -> bool:
    """True if the RS chart is above its own bullish support line."""
    return is_above_bullish_support(rs_chart)


def is_rs_negative_trend(rs_chart: PnFChart) -> bool:
    """True if the RS chart is below its own bearish resistance line."""
    return is_below_bearish_resistance(rs_chart)
