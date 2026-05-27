"""Rew/Risk ratio for a stock's RS chart vs. the market.

DWA reports a reward-to-risk reading for each security based on its
RS-vs-market P&F chart:

    Reward = price levels of overhead resistance the RS chart must clear
             to fire a new buy signal — i.e., distance from current RS
             level to the nearest unbroken prior X-column top above current.

    Risk   = distance from the current RS level down to the bullish
             support trendline (or the nearest prior O-column bottom below
             current if no BSL is drawable).

    Rew/Risk = Reward / Risk

This is a report-only field; it does not drive ranking.

If either side cannot be computed (e.g., no overhead resistance because
the stock is at an all-time RS high, no BSL because chart history is too
short), the function returns None — the report should show "n/a".
"""

from __future__ import annotations

from decimal import Decimal

from pnf_bot.pnf.trendlines import find_bullish_support_line
from pnf_bot.pnf.types import PnFChart


def compute_rs_rew_risk(rs_chart: PnFChart | None) -> Decimal | None:
    """Compute Rew/Risk for an RS chart. Returns None if not computable."""
    if rs_chart is None or not rs_chart.columns:
        return None

    current = rs_chart.columns[-1]
    current_level = current.top if current.type == "X" else current.bottom
    if current_level <= 0:
        return None

    reward_distance = _distance_to_overhead(rs_chart, current_level)
    risk_distance = _distance_to_support(rs_chart, current_level)

    if reward_distance is None or risk_distance is None:
        return None
    if risk_distance <= 0:
        return None

    return Decimal(str(round(float(reward_distance) / float(risk_distance), 2)))


def _distance_to_overhead(chart: PnFChart, current_level: Decimal) -> Decimal | None:
    """Find the lowest prior X-column top that is still above current level.

    Returns the distance from current to that level (positive value), or
    None if no overhead resistance exists (current is at or above every
    prior X top — i.e., at all-time chart high).
    """
    overheads: list[Decimal] = []
    for col in chart.columns[:-1]:  # exclude current column
        if col.type == "X" and col.top > current_level:
            overheads.append(col.top)
    if not overheads:
        return None
    nearest = min(overheads)
    return nearest - current_level


def _distance_to_support(chart: PnFChart, current_level: Decimal) -> Decimal | None:
    """Distance from current level down to support.

    Preference order:
    1. The bullish support line's value at the current column (if drawable).
    2. The nearest prior O-column bottom that is still below current.

    Returns positive distance, or None if no support is identifiable.
    """
    bsl = find_bullish_support_line(chart)
    if bsl is not None:
        current_col_idx = len(chart.columns) - 1
        bsl_value_at_current = bsl.price_at_column(current_col_idx)
        if bsl_value_at_current < current_level:
            return current_level - bsl_value_at_current

    # Fall back to nearest prior O bottom below current
    bottoms: list[Decimal] = []
    for col in chart.columns[:-1]:
        if col.type == "O" and col.bottom < current_level:
            bottoms.append(col.bottom)
    if not bottoms:
        return None
    nearest_bottom = max(bottoms)  # highest of the lower bottoms = nearest support
    return current_level - nearest_bottom
