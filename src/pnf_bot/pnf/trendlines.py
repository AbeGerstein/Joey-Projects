"""45° trendlines for P&F charts — bullish support and bearish resistance.

In Dorsey's framework:

**Bullish support line** — drawn at 45° upward from the lowest O of the
chart's most recent significant decline. Each step is one box up per column
to the right. Stays in force as long as price (subsequent O columns) doesn't
drop below it. A break is a major bearish event.

**Bearish resistance line** — drawn at 45° downward from the highest X of
the most recent significant rally. Each step is one box down per column.
Stays in force as long as price doesn't break above it.

This module exposes:
- `Trendline` dataclass: type, anchor point, slope, evaluator
- `find_bullish_support_line(chart)` — anchored at lowest O in lookback window
- `find_bearish_resistance_line(chart)` — anchored at highest X in lookback window
- Trend-posture helpers that the screening logic consumes:
  `is_above_bullish_support(chart)`, `is_below_bearish_resistance(chart)`,
  `boxes_above_bullish_support(chart)`, etc.

Implementation note: the slope uses additive math (one box of the ANCHOR
column's box_size per column to the right). For traditional scaling this
is exact within a tier; for percentage scaling it's a simplification that
works well over short ranges but drifts over many years. v1-acceptable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from pnf_bot.pnf.types import PnFChart

TrendlineType = Literal["bullish_support", "bearish_resistance"]


@dataclass(frozen=True)
class Trendline:
    """A 45° trendline on a P&F chart.

    Anchored at a specific column index and price level. The slope is
    additive: +box_size per column to the right (bullish_support) or
    -box_size per column to the right (bearish_resistance).
    """

    type: TrendlineType
    anchor_column_index: int
    anchor_price: Decimal
    box_size: Decimal
    anchor_date: date

    def price_at_column(self, column_index: int) -> Decimal:
        """Return the trendline's price level at a given column index.

        For columns before the anchor, the projection extrapolates backward —
        which is rarely useful but defined for completeness.
        """
        offset = Decimal(column_index - self.anchor_column_index)
        delta = offset * self.box_size
        if self.type == "bullish_support":
            return self.anchor_price + delta
        return self.anchor_price - delta


# ---------------------------------------------------------------------------
# Finding trendlines from a chart's history
# ---------------------------------------------------------------------------


def find_bullish_support_line(
    chart: PnFChart,
    lookback_columns: int | None = None,
) -> Trendline | None:
    """Find the bullish support line, anchored at the lowest recent O column.

    `lookback_columns` limits the search to the last N columns. None means
    search the entire chart.

    The line is anchored ONE column to the right of the lowest O (Dorsey's
    convention — the line starts from the column after the low) at price =
    lowest_o.bottom + lowest_o.box_size (one box above the low).

    Returns None if the chart has no O columns in the lookback window.
    """
    cols = chart.columns
    if not cols:
        return None
    if lookback_columns is not None and lookback_columns < len(cols):
        offset = len(cols) - lookback_columns
        window = cols[offset:]
    else:
        offset = 0
        window = cols

    candidates = [(i + offset, c) for i, c in enumerate(window) if c.type == "O"]
    if not candidates:
        return None

    lowest_idx, lowest_o = min(candidates, key=lambda t: t[1].bottom)
    anchor_idx = lowest_idx + 1  # one column after the lowest O
    return Trendline(
        type="bullish_support",
        anchor_column_index=anchor_idx,
        anchor_price=lowest_o.bottom + lowest_o.box_size,
        box_size=lowest_o.box_size,
        anchor_date=lowest_o.end_date,
    )


def find_bearish_resistance_line(
    chart: PnFChart,
    lookback_columns: int | None = None,
) -> Trendline | None:
    """Find the bearish resistance line, anchored at the highest recent X column.

    Mirror of find_bullish_support_line.
    """
    cols = chart.columns
    if not cols:
        return None
    if lookback_columns is not None and lookback_columns < len(cols):
        offset = len(cols) - lookback_columns
        window = cols[offset:]
    else:
        offset = 0
        window = cols

    candidates = [(i + offset, c) for i, c in enumerate(window) if c.type == "X"]
    if not candidates:
        return None

    highest_idx, highest_x = max(candidates, key=lambda t: t[1].top)
    anchor_idx = highest_idx + 1
    return Trendline(
        type="bearish_resistance",
        anchor_column_index=anchor_idx,
        anchor_price=highest_x.top - highest_x.box_size,
        box_size=highest_x.box_size,
        anchor_date=highest_x.end_date,
    )


# ---------------------------------------------------------------------------
# Trend-posture helpers consumed by the screening logic
# ---------------------------------------------------------------------------


def is_above_bullish_support(chart: PnFChart, lookback_columns: int | None = None) -> bool:
    """True if the chart's current column's bottom is above the bullish support line.

    Returns False if no support line can be drawn (insufficient history).
    """
    line = find_bullish_support_line(chart, lookback_columns)
    if line is None or not chart.columns:
        return False
    current_idx = len(chart.columns) - 1
    return chart.columns[current_idx].bottom >= line.price_at_column(current_idx)


def is_below_bearish_resistance(chart: PnFChart, lookback_columns: int | None = None) -> bool:
    """True if the chart's current column's top is below the bearish resistance line."""
    line = find_bearish_resistance_line(chart, lookback_columns)
    if line is None or not chart.columns:
        return False
    current_idx = len(chart.columns) - 1
    return chart.columns[current_idx].top <= line.price_at_column(current_idx)


def boxes_above_bullish_support(chart: PnFChart, lookback_columns: int | None = None) -> int:
    """How many boxes is the current column above the bullish support line?

    Returns 0 if no line exists or the current column is at/below the line.
    Useful for "extended" anti-pattern detection — large values flag
    a chart that has rallied far past its support.
    """
    line = find_bullish_support_line(chart, lookback_columns)
    if line is None or not chart.columns:
        return 0
    current_idx = len(chart.columns) - 1
    current = chart.columns[current_idx]
    line_price = line.price_at_column(current_idx)
    if current.top < line_price:
        return 0
    return int((current.top - line_price) / current.box_size)


def boxes_below_bearish_resistance(
    chart: PnFChart, lookback_columns: int | None = None
) -> int:
    """How many boxes is the current column below the bearish resistance line?

    Returns 0 if no line exists or the current column is at/above the line.
    """
    line = find_bearish_resistance_line(chart, lookback_columns)
    if line is None or not chart.columns:
        return 0
    current_idx = len(chart.columns) - 1
    current = chart.columns[current_idx]
    line_price = line.price_at_column(current_idx)
    if current.bottom > line_price:
        return 0
    return int((line_price - current.bottom) / current.box_size)
