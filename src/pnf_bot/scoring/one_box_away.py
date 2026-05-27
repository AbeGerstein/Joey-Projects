"""One-box-away pattern detection.

Used by the checklist methodology to build List 2 ("stocks where the price
chart is one box from firing one of the qualifying patterns") and the W1
weight ("stock is one box from a new RS-vs-market buy signal").

Approach: simulate adding exactly one X box to the chart's current X column.
Run the existing signal detectors on the simulated chart. Any signal that
fires in the simulated state but NOT in the actual state is something the
stock is "one box away from."

If the chart's current column is an O column, the next X box requires a
3-box reversal first — that's more than "one box away" by the strict
interpretation, so this module returns an empty set for those charts.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from pnf_bot.pnf.signals import Signal, SignalType, detect_signals
from pnf_bot.pnf.types import PnFChart

# The patterns the checklist methodology cares about. Double_top is
# explicitly excluded per the advisor's spec.
CHECKLIST_QUALIFYING_PATTERNS: frozenset[SignalType] = frozenset(
    {
        "triple_top",
        "quadruple_top",
        "quintuple_top",
        "spread_triple_top",
        "spread_quadruple_top",
        "spread_quintuple_top",
        "shakeout",
        "bullish_triangle",
        "bullish_catapult",
        "bearish_signal_reversal",
    }
)


def fired_today(
    signals: Iterable[Signal],
    as_of_date,  # noqa: ANN001
    patterns: frozenset[SignalType] = CHECKLIST_QUALIFYING_PATTERNS,
) -> set[SignalType]:
    """Return the subset of `patterns` that fired on the most recent trading day.

    A signal "fires today" if its fired_date == as_of_date. For weekend / non-trading
    `as_of_date` values the caller should pre-adjust (typically as_of_date = the
    chart's latest column.end_date).
    """
    fired: set[SignalType] = set()
    for s in signals:
        if s.type in patterns and s.fired_date == as_of_date:
            fired.add(s.type)
    return fired


def one_box_away(
    chart: PnFChart,
    patterns: frozenset[SignalType] = CHECKLIST_QUALIFYING_PATTERNS,
) -> set[SignalType]:
    """Return the subset of `patterns` the chart would fire if its current
    X column gained one more box.

    If the current column is O (selling), return empty set — those charts
    need a reversal before any X-side pattern is reachable.
    """
    if not chart.columns:
        return set()
    current = chart.columns[-1]
    if current.type != "X":
        return set()

    # What's currently firing on this chart at the current column?
    current_signals = detect_signals(chart)
    current_types_at_latest = {
        s.type
        for s in current_signals
        if s.column_index == len(chart.columns) - 1 and s.type in patterns
    }

    simulated = _simulate_one_more_x_box(chart)
    simulated_signals = detect_signals(simulated)
    simulated_types_at_latest = {
        s.type
        for s in simulated_signals
        if s.column_index == len(simulated.columns) - 1 and s.type in patterns
    }

    # New patterns in simulated that aren't already firing on actual
    return simulated_types_at_latest - current_types_at_latest


def _simulate_one_more_x_box(chart: PnFChart) -> PnFChart:
    """Return a copy of `chart` with the current X column extended by 1 box.

    Caller must verify chart has at least one column and current is X.
    """
    cols = list(chart.columns)
    current = cols[-1]
    new_top = current.top + current.box_size
    new_current = replace(current, top=new_top)
    cols[-1] = new_current
    return PnFChart(
        symbol=chart.symbol,
        columns=tuple(cols),
        box_scaling_label=chart.box_scaling_label,
        reversal_boxes=chart.reversal_boxes,
    )


def one_box_away_from_rs_buy(rs_chart: PnFChart | None) -> bool:
    """True if the RS chart's current X column would fire a new bullish
    signal with one more box of advance.

    Used for the checklist W1 (vs market) and W2 (vs sector) weights.
    Returns False if rs_chart is None or current col is O.

    "New bullish signal" = any bullish signal that doesn't already fire
    on the current column. We deliberately scope this broadly (DT, TT,
    catapult, triangle, etc.) since any new buy signal on the RS chart
    is meaningful for the regime.
    """
    if rs_chart is None or not rs_chart.columns:
        return False
    current = rs_chart.columns[-1]
    if current.type != "X":
        return False

    current_signals = detect_signals(rs_chart)
    current_bullish_at_latest = {
        s.type
        for s in current_signals
        if s.column_index == len(rs_chart.columns) - 1 and s.is_bullish
    }

    simulated = _simulate_one_more_x_box(rs_chart)
    simulated_signals = detect_signals(simulated)
    simulated_bullish_at_latest = {
        s.type
        for s in simulated_signals
        if s.column_index == len(simulated.columns) - 1 and s.is_bullish
    }

    return bool(simulated_bullish_at_latest - current_bullish_at_latest)
