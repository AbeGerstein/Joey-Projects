"""Bullish Percent Index (BPI) computation and market-state classification.

The BPI is the percentage of stocks in a universe currently on a P&F buy
signal. It is the canonical market-breadth indicator in Dorsey's methodology
and a key input to the bot's "sector tailwind" scoring component.

Per the methodology doc:
- BPI = (count of stocks on a buy signal / total stocks in universe) × 100
- BPI is itself plotted as a P&F chart with 2% boxes and 3-box reversal
- Six market states are derived from the BPI P&F chart's column direction
  and position (Bull Confirmed, Bull Correction, Bull Alert, Bear Confirmed,
  Bear Correction, Bear Alert)

Sector BPIs are computed identically — just over a sector subset of the
universe. The 11 GICS sectors (from Norgate) each get their own BPI series.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

import pandas as pd

from pnf_bot.pnf.box_scaling import BoxScaling
from pnf_bot.pnf.chart import construct_chart
from pnf_bot.pnf.signals import detect_signals
from pnf_bot.pnf.types import PnFChart

# BPI box size on the BPI's own P&F chart — 2 percentage points per box,
# per Dorsey's convention. Plotted as a custom BoxScaling below.
BPI_BOX_SIZE = Decimal("2")
BPI_REVERSAL = 3

SignalPosture = Literal["buy", "sell", "unknown"]

BpiState = Literal[
    "bull_confirmed",
    "bull_correction",
    "bull_alert",
    "bear_confirmed",
    "bear_correction",
    "bear_alert",
    "unknown",
]


# Six-state classifier thresholds (per Dorsey)
BPI_HIGH_RISK_LEVEL = Decimal("70")   # above this = overbought zone
BPI_LOW_RISK_LEVEL = Decimal("30")    # below this = oversold zone


@dataclass(frozen=True)
class BpiPoint:
    """One day's BPI snapshot."""

    snapshot_date: date
    bpi_value: Decimal             # 0-100 percentage
    total_stocks: int
    stocks_on_buy_signal: int


# ---------------------------------------------------------------------------
# Per-stock posture helper
# ---------------------------------------------------------------------------


def current_signal_posture(chart: PnFChart) -> SignalPosture:
    """Return the chart's CURRENT P&F signal posture.

    Walks the chart's signals (sorted chronologically) and returns the
    direction of the most recent one. Returns "unknown" if the chart
    has no signals yet (e.g., very short history).
    """
    signals = detect_signals(chart)
    if not signals:
        return "unknown"
    most_recent = signals[-1]
    return "buy" if most_recent.is_bullish else "sell"


# ---------------------------------------------------------------------------
# BPI computation
# ---------------------------------------------------------------------------


def compute_bpi(charts: dict[str, PnFChart]) -> Decimal:
    """Compute the BPI from a dict mapping symbol -> PnFChart.

    Returns a Decimal in [0, 100] representing the percentage of stocks
    currently on a P&F buy signal. Stocks with no detectable signal
    history (posture = "unknown") are excluded from both the numerator
    and the denominator.

    Returns 0 if no stocks have a determinable posture.
    """
    determinable = 0
    on_buy = 0
    for chart in charts.values():
        posture = current_signal_posture(chart)
        if posture == "buy":
            on_buy += 1
            determinable += 1
        elif posture == "sell":
            determinable += 1
    if determinable == 0:
        return Decimal("0")
    return (Decimal(on_buy) / Decimal(determinable) * Decimal("100")).quantize(
        Decimal("0.01")
    )


def compute_bpi_with_breakdown(charts: dict[str, PnFChart]) -> BpiPoint:
    """Same as compute_bpi but returns a structured BpiPoint with breakdown."""
    determinable = 0
    on_buy = 0
    for chart in charts.values():
        posture = current_signal_posture(chart)
        if posture == "buy":
            on_buy += 1
            determinable += 1
        elif posture == "sell":
            determinable += 1
    if determinable == 0:
        bpi = Decimal("0")
    else:
        bpi = (Decimal(on_buy) / Decimal(determinable) * Decimal("100")).quantize(
            Decimal("0.01")
        )
    return BpiPoint(
        snapshot_date=date.today(),
        bpi_value=bpi,
        total_stocks=determinable,
        stocks_on_buy_signal=on_buy,
    )


# ---------------------------------------------------------------------------
# Six-state classifier
# ---------------------------------------------------------------------------


def classify_bpi_state(bpi_chart: PnFChart) -> BpiState:
    """Classify the BPI's market state per Dorsey's six-state framework.

    Inputs the BPI's own P&F chart (constructed via `construct_bpi_chart`).

    State definitions:
    - Bull Confirmed: BPI is in an X column AND no recent break to a sell signal
    - Bull Correction: was Bull Confirmed, but BPI has reversed into an O column
    - Bull Alert: BPI dropped below 30%, then reversed up into a new X column
    - Bear Confirmed: BPI in O column AND no recent break to a buy signal
    - Bear Correction: was Bear Confirmed, but BPI reversed into an X column
    - Bear Alert: BPI rose above 70%, then reversed down into a new O column

    Returns "unknown" if the chart has no columns.
    """
    if not bpi_chart.columns:
        return "unknown"

    current = bpi_chart.columns[-1]
    signals = detect_signals(bpi_chart)
    last_signal = signals[-1] if signals else None
    most_recent_bullish_value = _highest_x_top(bpi_chart)

    if current.type == "X":
        # BPI is rising
        if last_signal and last_signal.is_bearish:
            # Most recent signal was a sell — this rising X is a correction
            return "bear_correction"
        # Check for Bull Alert: BPI was below 30%, now reversing up
        if (
            most_recent_bullish_value is not None
            and current.top <= BPI_LOW_RISK_LEVEL + Decimal("10")
            and _was_recently_below(bpi_chart, BPI_LOW_RISK_LEVEL)
        ):
            return "bull_alert"
        return "bull_confirmed"

    # O column — BPI is falling
    if last_signal and last_signal.is_bullish:
        # Most recent signal was a buy — this falling O is a correction
        return "bull_correction"
    # Check for Bear Alert: BPI was above 70%, now reversing down
    if _was_recently_above(bpi_chart, BPI_HIGH_RISK_LEVEL):
        return "bear_alert"
    return "bear_confirmed"


def _highest_x_top(chart: PnFChart) -> Decimal | None:
    """Return the highest top across all X columns in the chart."""
    x_tops = [c.top for c in chart.columns if c.type == "X"]
    return max(x_tops) if x_tops else None


def _was_recently_below(chart: PnFChart, threshold: Decimal, lookback: int = 5) -> bool:
    """True if any column in the last `lookback` columns had its bottom below threshold."""
    recent = chart.columns[-lookback:] if len(chart.columns) > lookback else chart.columns
    return any(c.bottom < threshold for c in recent)


def _was_recently_above(chart: PnFChart, threshold: Decimal, lookback: int = 5) -> bool:
    """True if any column in the last `lookback` columns had its top above threshold."""
    recent = chart.columns[-lookback:] if len(chart.columns) > lookback else chart.columns
    return any(c.top > threshold for c in recent)


# ---------------------------------------------------------------------------
# BPI history series and chart construction
# ---------------------------------------------------------------------------


def construct_bpi_chart(bpi_history: pd.Series, symbol: str = "BPI") -> PnFChart:
    """Build a P&F chart of the BPI series itself, using 2% boxes.

    `bpi_history` is a pandas Series indexed by date with BPI values (0-100).
    Each day's BPI is treated as both high and low for the P&F construction
    (the BPI doesn't have an intraday range to estimate).
    """
    ohlc = pd.DataFrame(
        {
            "high": bpi_history.values,
            "low": bpi_history.values,
            "open": bpi_history.values,
            "close": bpi_history.values,
            "volume": 0,
        },
        index=bpi_history.index,
    )
    return construct_chart(
        symbol=symbol,
        ohlc=ohlc,
        scaling=_BpiScaling(),
        reversal_boxes=BPI_REVERSAL,
    )


class _BpiScaling(BoxScaling):
    """BPI uses fixed 2-percentage-point boxes regardless of the BPI value.

    The BPI ranges from 0 to 100 and the standard P&F convention is 2
    percentage points per box. This is additive, not multiplicative
    (unlike RS percentage scaling).
    """

    def label(self) -> str:
        return f"bpi:{BPI_BOX_SIZE}pp"

    def box_size_at(self, price: Decimal) -> Decimal:
        return BPI_BOX_SIZE

    def snap_floor(self, price: Decimal) -> Decimal:
        from decimal import ROUND_FLOOR

        n = (price / BPI_BOX_SIZE).quantize(Decimal("1"), rounding=ROUND_FLOOR)
        return n * BPI_BOX_SIZE

    def snap_ceiling(self, price: Decimal) -> Decimal:
        floor = self.snap_floor(price)
        return floor if floor == price else floor + BPI_BOX_SIZE

    def box_above(self, price: Decimal) -> Decimal:
        return price + BPI_BOX_SIZE

    def box_below(self, price: Decimal) -> Decimal:
        return price - BPI_BOX_SIZE

    def boxes_between(self, lower: Decimal, upper: Decimal) -> int:
        if upper < lower:
            return 0
        from decimal import ROUND_FLOOR

        return int(
            ((upper - lower) / BPI_BOX_SIZE).quantize(
                Decimal("1"), rounding=ROUND_FLOOR
            )
        )
