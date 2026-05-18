"""Foundational P&F signal detection.

Implements the basic and continuation signals from Dorsey's *Point and
Figure Charting*:

| Signal | Direction | Definition |
|---|---|---|
| Double Top (DT) | Bullish | Current X column rises one box above the immediately preceding X column's top |
| Double Bottom (DB) | Bearish | Current O column falls one box below the immediately preceding O column's bottom |
| Triple Top (TT) | Bullish | Current X column exceeds the tops of two prior X columns at the same level |
| Triple Bottom (TB) | Bearish | Current O column drops below the bottoms of two prior O columns at the same level |
| Spread Triple Top | Bullish | Three prior X columns hit similar (within a tolerance) but not identical tops; current X exceeds all |
| Spread Triple Bottom | Bearish | Mirror of Spread Triple Top |

Each signal carries:
- `type`: the signal kind
- `direction`: bullish or bearish
- `column_index`: which column produced the signal
- `fired_date`: the date the signal was confirmed (price first crossed the breakout level)
- `price_level`: the price at which the signal fired

For a freshness check ("did this fire last night?"), compare
signal.fired_date against the last trading day.

Compound signals (catapult, triangle, long tail) come in Phase 2C —
they build on these foundational detectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from pnf_bot.pnf.types import Column, ColumnType, PnFChart

SignalType = Literal[
    "double_top",
    "double_bottom",
    "triple_top",
    "triple_bottom",
    "spread_triple_top",
    "spread_triple_bottom",
]

SignalDirection = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class Signal:
    """A P&F signal event fired by a chart pattern."""

    type: SignalType
    direction: SignalDirection
    column_index: int
    fired_date: date
    price_level: Decimal

    @property
    def is_bullish(self) -> bool:
        return self.direction == "bullish"

    @property
    def is_bearish(self) -> bool:
        return self.direction == "bearish"


# How many boxes apart two prior column extremes can be and still count
# as a "spread" triple top/bottom. Two-box tolerance is a common choice
# in the P&F literature; configurable per call if needed.
DEFAULT_SPREAD_TOLERANCE_BOXES = 2


def detect_signals(
    chart: PnFChart,
    spread_tolerance_boxes: int = DEFAULT_SPREAD_TOLERANCE_BOXES,
) -> list[Signal]:
    """Walk the chart's columns and return every foundational signal that fired.

    Signals are returned in chronological order. A single column may produce
    multiple signals (e.g., the same X column may register both a DT and a TT
    if it breaks through one prior top, then through two).
    """
    signals: list[Signal] = []
    for i, column in enumerate(chart.columns):
        if column.type == "X":
            signals.extend(_detect_x_signals(chart, i, spread_tolerance_boxes))
        else:
            signals.extend(_detect_o_signals(chart, i, spread_tolerance_boxes))
    # Sort by fire date for determinism
    signals.sort(key=lambda s: (s.fired_date, s.column_index, s.type))
    return signals


def latest_signal(chart: PnFChart) -> Signal | None:
    """Return the most recently fired signal in the chart, or None if no signals."""
    signals = detect_signals(chart)
    return signals[-1] if signals else None


# ---------------------------------------------------------------------------
# X-column signal detection
# ---------------------------------------------------------------------------


def _detect_x_signals(
    chart: PnFChart, current_idx: int, spread_tolerance_boxes: int
) -> list[Signal]:
    """Return signals fired by the X column at `current_idx`."""
    current = chart.columns[current_idx]
    if current.type != "X":
        return []
    box = current.box_size

    # Collect prior X columns by walking backwards. Columns alternate X/O so
    # prior X columns are at current_idx - 2, current_idx - 4, ...
    prior_x_cols = _prior_columns_of_type(chart.columns, current_idx, "X")

    signals: list[Signal] = []

    # --- Double Top ---
    if prior_x_cols:
        prior = prior_x_cols[0]  # immediately preceding X column
        signal_level = prior.top + box
        if current.top >= signal_level:
            fired = current.date_when_extreme_reached(signal_level) or current.end_date
            signals.append(
                Signal(
                    type="double_top",
                    direction="bullish",
                    column_index=current_idx,
                    fired_date=fired,
                    price_level=signal_level,
                )
            )

    # --- Triple Top: two prior X columns at the SAME top, current exceeds ---
    if len(prior_x_cols) >= 2:
        prior_1 = prior_x_cols[0]
        prior_2 = prior_x_cols[1]
        if prior_1.top == prior_2.top:
            signal_level = prior_1.top + box
            if current.top >= signal_level:
                fired = current.date_when_extreme_reached(signal_level) or current.end_date
                signals.append(
                    Signal(
                        type="triple_top",
                        direction="bullish",
                        column_index=current_idx,
                        fired_date=fired,
                        price_level=signal_level,
                    )
                )

    # --- Spread Triple Top: two prior X columns at SIMILAR (within tolerance) tops ---
    if len(prior_x_cols) >= 2:
        prior_1 = prior_x_cols[0]
        prior_2 = prior_x_cols[1]
        # Exclude exact-match case (that's a regular Triple Top, not spread)
        if prior_1.top != prior_2.top:
            top_diff_boxes = abs(prior_1.top - prior_2.top) / box
            if Decimal("0") < top_diff_boxes <= Decimal(spread_tolerance_boxes):
                # Current must exceed BOTH prior tops by at least one box
                highest_prior = max(prior_1.top, prior_2.top)
                signal_level = highest_prior + box
                if current.top >= signal_level:
                    fired = (
                        current.date_when_extreme_reached(signal_level) or current.end_date
                    )
                    signals.append(
                        Signal(
                            type="spread_triple_top",
                            direction="bullish",
                            column_index=current_idx,
                            fired_date=fired,
                            price_level=signal_level,
                        )
                    )

    return signals


# ---------------------------------------------------------------------------
# O-column signal detection (mirror of X)
# ---------------------------------------------------------------------------


def _detect_o_signals(
    chart: PnFChart, current_idx: int, spread_tolerance_boxes: int
) -> list[Signal]:
    """Return signals fired by the O column at `current_idx`."""
    current = chart.columns[current_idx]
    if current.type != "O":
        return []
    box = current.box_size

    prior_o_cols = _prior_columns_of_type(chart.columns, current_idx, "O")

    signals: list[Signal] = []

    # --- Double Bottom ---
    if prior_o_cols:
        prior = prior_o_cols[0]
        signal_level = prior.bottom - box
        if current.bottom <= signal_level:
            fired = current.date_when_extreme_reached(signal_level) or current.end_date
            signals.append(
                Signal(
                    type="double_bottom",
                    direction="bearish",
                    column_index=current_idx,
                    fired_date=fired,
                    price_level=signal_level,
                )
            )

    # --- Triple Bottom ---
    if len(prior_o_cols) >= 2:
        prior_1 = prior_o_cols[0]
        prior_2 = prior_o_cols[1]
        if prior_1.bottom == prior_2.bottom:
            signal_level = prior_1.bottom - box
            if current.bottom <= signal_level:
                fired = current.date_when_extreme_reached(signal_level) or current.end_date
                signals.append(
                    Signal(
                        type="triple_bottom",
                        direction="bearish",
                        column_index=current_idx,
                        fired_date=fired,
                        price_level=signal_level,
                    )
                )

    # --- Spread Triple Bottom ---
    if len(prior_o_cols) >= 2:
        prior_1 = prior_o_cols[0]
        prior_2 = prior_o_cols[1]
        if prior_1.bottom != prior_2.bottom:
            bottom_diff_boxes = abs(prior_1.bottom - prior_2.bottom) / box
            if Decimal("0") < bottom_diff_boxes <= Decimal(spread_tolerance_boxes):
                lowest_prior = min(prior_1.bottom, prior_2.bottom)
                signal_level = lowest_prior - box
                if current.bottom <= signal_level:
                    fired = (
                        current.date_when_extreme_reached(signal_level) or current.end_date
                    )
                    signals.append(
                        Signal(
                            type="spread_triple_bottom",
                            direction="bearish",
                            column_index=current_idx,
                            fired_date=fired,
                            price_level=signal_level,
                        )
                    )

    return signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prior_columns_of_type(
    columns: tuple[Column, ...], current_idx: int, column_type: ColumnType
) -> list[Column]:
    """Return prior columns of the given type, in reverse chronological order.

    The chart's columns alternate X/O/X/O, so prior columns of the same
    type as the current are at indices current_idx - 2, current_idx - 4, ...
    """
    result: list[Column] = []
    i = current_idx - 2
    while i >= 0:
        if columns[i].type == column_type:
            result.append(columns[i])
        i -= 2
    return result
