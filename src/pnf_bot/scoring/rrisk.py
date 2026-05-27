"""Rrisk — relative risk vs. the S&P 500.

Per DWA's glossary: Rrisk is the standard deviation of the security
divided by the standard deviation of SPX. Similar to a beta measure
without factoring in correlation.

    Rrisk = σ(stock daily returns) / σ(SPX daily returns)

over a rolling window (252 trading days = 1 year by convention, the
DWA default for risk metrics derived from daily data).

Interpretation:
- Rrisk > 1 → security has greater-than-market daily volatility
- Rrisk < 1 → security has lower-than-market daily volatility
- Rrisk = 1 → similar to S&P

This is a report-only field; it does not drive ranking.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

DEFAULT_WINDOW_DAYS = 252


def compute_rrisk(
    stock_ohlc: pd.DataFrame,
    spx_ohlc: pd.DataFrame,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> Decimal | None:
    """Compute Rrisk = σ_stock / σ_SPX over the most recent `window_days`.

    Both inputs must have a `close` column. Returns are computed as
    log returns over consecutive trading days.

    Returns the ratio as a Decimal, or None if either side lacks enough
    history or σ_SPX is zero.
    """
    if stock_ohlc.empty or "close" not in stock_ohlc.columns:
        return None
    if spx_ohlc.empty or "close" not in spx_ohlc.columns:
        return None

    stock_returns = _log_returns(stock_ohlc["close"], window_days)
    spx_returns = _log_returns(spx_ohlc["close"], window_days)

    if stock_returns is None or spx_returns is None:
        return None

    sigma_stock = stock_returns.std(ddof=0)
    sigma_spx = spx_returns.std(ddof=0)

    if sigma_spx == 0 or not np.isfinite(sigma_spx):
        return None
    if not np.isfinite(sigma_stock):
        return None

    return Decimal(str(round(float(sigma_stock) / float(sigma_spx), 3)))


def _log_returns(closes: pd.Series, window_days: int) -> pd.Series | None:
    """Compute log returns of the last `window_days + 1` closes (yielding
    `window_days` returns). Returns None if insufficient history.
    """
    closes_f = closes.astype(float)
    if len(closes_f) < window_days + 1:
        return None
    window = closes_f.iloc[-(window_days + 1):]
    returns = np.log(window / window.shift(1)).dropna()
    if len(returns) < window_days:
        return None
    return returns
