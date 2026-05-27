"""Weekly OBOS% (Overbought/Oversold) — DWA's 10-week trading-band reading.

Per DWA's documentation, the Weekly OBOS% measures a security's position
within a 10-week trading band:

- 0%   → price at the 50-day (10-week) moving average
- +100% → price at the upper band (overbought)
- -100% → price at the lower band (oversold)

Values can exceed ±100% in strongly trending or extreme moves.

DWA's exact band-width formula is not published. The standard reproduction
that fits the described semantics is a Bollinger-band-style calculation
using ±2 standard deviations over the same 50-day window:

    OBOS% = (Close - 50d_MA) / (2 × 50d_std) × 100

This produces ±100% at ±2σ from the MA — a common technical-analysis
overbought/oversold threshold. The 115% gate the bot uses (hard
elimination above 115% overbought) maps to roughly +2.3σ which is the
"extended" zone in most practitioners' usage.

If you have access to DWA's actual published OBOS for a known ticker on
a known date, this can be calibrated by comparing the formula's output
to ground truth and adjusting the band-width constant.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

DEFAULT_WINDOW_DAYS = 50
DEFAULT_BAND_SIGMAS = Decimal("2")


def compute_obos(
    ohlc: pd.DataFrame,
    window_days: int = DEFAULT_WINDOW_DAYS,
    band_sigmas: Decimal = DEFAULT_BAND_SIGMAS,
) -> Decimal | None:
    """Compute the most recent Weekly OBOS% reading for a stock.

    Inputs:
        ohlc: DataFrame with a `close` column, indexed by trade date.
        window_days: lookback for the moving average and standard deviation.
            Default 50 trading days (~10 weeks).
        band_sigmas: standard deviations used to define the ±100% band.
            Default 2 (Bollinger-band convention).

    Returns:
        The latest OBOS% reading as a Decimal, or None if there is not
        enough history for the moving average. Positive = overbought,
        negative = oversold.
    """
    if ohlc.empty or "close" not in ohlc.columns:
        return None
    if len(ohlc) < window_days:
        return None

    closes = ohlc["close"].astype(float)
    window = closes.iloc[-window_days:]
    ma = window.mean()
    std = window.std(ddof=0)
    if std == 0:
        return Decimal("0")

    latest_close = float(closes.iloc[-1])
    obos = (latest_close - ma) / (float(band_sigmas) * std) * 100.0
    return Decimal(str(round(obos, 2)))


def is_above_hard_overbought(obos: Decimal | None, threshold: Decimal = Decimal("115")) -> bool:
    """Return True if OBOS exceeds the hard-elimination threshold.

    Per the advisor's spec: stocks above 115% overbought are eliminated
    from ranking regardless of other factors.

    None inputs (e.g., insufficient history) return False — we don't
    eliminate stocks just for missing OBOS data.
    """
    if obos is None:
        return False
    return obos > threshold


def obos_weight(obos: Decimal | None, max_weight: Decimal = Decimal("1.0")) -> Decimal:
    """Convert an OBOS reading to a weighting contribution (0.0 to max_weight).

    Lower OBOS = higher weight (less overbought is more attractive). At
    or below -100% (deeply oversold), returns max_weight. At +115% (the
    hard cut), returns 0. Linear interpolation between.

    Stocks above the hard cut should be filtered out BEFORE calling this;
    this function returns 0 for them defensively but the filter is the
    primary mechanism.

    None inputs return 0.5 × max_weight (neutral when data is missing).
    """
    if obos is None:
        return max_weight * Decimal("0.5")
    # Clamp into [-100, 115] and map linearly to [max_weight, 0]
    if obos > Decimal("115"):
        return Decimal("0")
    if obos < Decimal("-100"):
        return max_weight
    span = Decimal("215")  # 115 - (-100)
    distance_from_cut = Decimal("115") - obos
    return (distance_from_cut / span) * max_weight
