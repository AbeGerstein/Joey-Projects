"""In-momentum pattern detectors (Section B of the daily report).

Implements the 6 patterns from docs/methodology/in-momentum-detection.md.
Stocks already in strong momentum that the advisor may want to buy into.

Patterns:
1. Recent buy signal still close to the breakout level
2. On buy signal + positive trend + RS positive (the "5-for-5'er" / strong-posture pattern)
3. Pole pattern — continuation after a 50% pullback
4. Fresh triangle breakout (the just-fired bullish_triangle signal)
5. Catapult confirmed (the just-fired bullish_catapult signal)
6. RS strengthening on already-positive chart (RS turning more positive while price is positive)

A stock with any in-momentum pattern is a Section B candidate UNLESS
also flagged by anti_patterns as exhausted (parabolic, blow-off, etc.).

Aggregated via detect_in_momentum_patterns(...) — call once per stock.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pnf_bot.pnf.rs import rs_signal_status
from pnf_bot.pnf.signals import detect_signals, latest_signal
from pnf_bot.pnf.trendlines import is_above_bullish_support
from pnf_bot.pnf.types import PnFChart
from pnf_bot.scoring.types import PatternMatch

InMomentumPatternType = Literal[
    "recent_buy_still_close",
    "strong_posture_5_for_5",
    "pole_pattern_continuation",
    "fresh_triangle_breakout",
    "catapult_confirmed",
    "rs_strengthening_on_positive",
]


# Configuration defaults
DEFAULT_RECENT_BUY_MAX_BOXES_ABOVE = 5
DEFAULT_RECENT_BUY_MAX_COLUMNS_AGO = 3
DEFAULT_POLE_MIN_BOXES = 10
DEFAULT_POLE_PULLBACK_MIN_RETRACE = Decimal("0.40")
DEFAULT_POLE_PULLBACK_MAX_RETRACE = Decimal("0.60")


def detect_in_momentum_patterns(
    price_chart: PnFChart,
    rs_chart: PnFChart | None = None,
    as_of_date: date | None = None,
) -> list[PatternMatch]:
    """Run all 6 in-momentum detectors. Returns every pattern currently active.

    Anti-pattern exclusions are NOT applied here — callers should check
    anti_patterns.is_exhausted(...) separately to filter Section B
    candidates that are past the point of responsible entry.
    """
    matches: list[PatternMatch] = []

    recent_buy = detect_recent_buy_still_close(price_chart)
    if recent_buy:
        matches.append(recent_buy)

    strong = detect_strong_posture(price_chart, rs_chart)
    if strong:
        matches.append(strong)

    pole = detect_pole_pattern_continuation(price_chart)
    if pole:
        matches.append(pole)

    fresh_triangle = detect_fresh_triangle_breakout(price_chart)
    if fresh_triangle:
        matches.append(fresh_triangle)

    catapult = detect_catapult_confirmed(price_chart)
    if catapult:
        matches.append(catapult)

    if rs_chart is not None:
        rs_strong = detect_rs_strengthening_on_positive(price_chart, rs_chart)
        if rs_strong:
            matches.append(rs_strong)

    return matches


# ---------------------------------------------------------------------------
# 1. Recent buy signal still close to breakout level
# ---------------------------------------------------------------------------


def detect_recent_buy_still_close(
    chart: PnFChart,
    max_boxes_above: int = DEFAULT_RECENT_BUY_MAX_BOXES_ABOVE,
    max_columns_ago: int = DEFAULT_RECENT_BUY_MAX_COLUMNS_AGO,
) -> PatternMatch | None:
    """A recent bullish signal where current price is still within
    `max_boxes_above` boxes of the signal level.

    Captures "the breakout has fired but the move hasn't extended yet" —
    the canonical "enter on confirmation, not extended" Section B setup.
    """
    cols = chart.columns
    if not cols:
        return None

    signals = detect_signals(chart)
    bullish = [s for s in signals if s.is_bullish]
    if not bullish:
        return None
    most_recent = bullish[-1]
    columns_ago = len(cols) - 1 - most_recent.column_index
    if columns_ago > max_columns_ago:
        return None

    current = cols[-1]
    if current.type != "X":
        return None
    distance = current.top - most_recent.price_level
    if distance < 0:
        return None
    boxes_above = int(distance / current.box_size)
    if boxes_above > max_boxes_above:
        return None

    strength = max(0.5, 1.0 - boxes_above / max(1, max_boxes_above))
    return PatternMatch(
        pattern_type="recent_buy_still_close",
        detected_date=current.end_date,
        description=(
            f"{most_recent.type} fired at {most_recent.price_level} "
            f"{columns_ago} column(s) ago; current top {current.top} "
            f"is {boxes_above} box(es) above signal"
        ),
        strength=strength,
    )


# ---------------------------------------------------------------------------
# 2. Strong posture (5-for-5'er equivalent)
# ---------------------------------------------------------------------------


def detect_strong_posture(
    price_chart: PnFChart, rs_chart: PnFChart | None = None
) -> PatternMatch | None:
    """All of: on buy signal, above bullish support, RS on buy signal.

    The "5-for-5'er" pattern in DWA terminology — a stock with every
    favorable condition satisfied. Section B's flagship pattern.
    """
    sig = latest_signal(price_chart)
    if sig is None or not sig.is_bullish:
        return None
    if not is_above_bullish_support(price_chart):
        return None
    if rs_chart is not None and rs_signal_status(rs_chart) != "buy":
        return None

    current = price_chart.columns[-1]
    return PatternMatch(
        pattern_type="strong_posture_5_for_5",
        detected_date=current.end_date,
        description=(
            f"Strong posture: on {sig.type}, above bullish support, "
            f"RS regime favorable"
        ),
        strength=1.0,
    )


# ---------------------------------------------------------------------------
# 3. Pole pattern continuation
# ---------------------------------------------------------------------------


def detect_pole_pattern_continuation(
    chart: PnFChart,
    pole_min_boxes: int = DEFAULT_POLE_MIN_BOXES,
    pullback_min_retrace: Decimal = DEFAULT_POLE_PULLBACK_MIN_RETRACE,
    pullback_max_retrace: Decimal = DEFAULT_POLE_PULLBACK_MAX_RETRACE,
) -> PatternMatch | None:
    """An X column of >=pole_min_boxes (the "pole") followed by an O
    column that retraced 40-60% of the pole, followed by an X column
    that has just exceeded the pole's top.

    Dorsey's continuation pattern — the resumption after a healthy pullback.
    """
    cols = chart.columns
    if len(cols) < 3:
        return None

    # Walk recent X columns looking for a pole
    for i in range(len(cols) - 3, -1, -1):
        candidate = cols[i]
        if candidate.type != "X":
            continue
        if candidate.height_boxes < pole_min_boxes:
            continue
        # Next column should be the O pullback
        if i + 1 >= len(cols) or cols[i + 1].type != "O":
            continue
        pullback = cols[i + 1]
        pole_height = candidate.top - candidate.bottom
        if pole_height <= 0:
            continue
        retrace = (candidate.top - pullback.bottom) / pole_height
        if not (pullback_min_retrace <= retrace <= pullback_max_retrace):
            continue
        # The following column should be the resumption X
        if i + 2 >= len(cols) or cols[i + 2].type != "X":
            continue
        resumption = cols[i + 2]
        # Resumption should have exceeded the pole's top
        if resumption.top <= candidate.top:
            continue
        return PatternMatch(
            pattern_type="pole_pattern_continuation",
            detected_date=resumption.end_date,
            description=(
                f"Pole pattern: {candidate.height_boxes}-box X column, "
                f"{retrace:.1%} retracement, resumption exceeded pole top"
            ),
            strength=1.0,
        )
    return None


# ---------------------------------------------------------------------------
# 4. Fresh triangle breakout
# ---------------------------------------------------------------------------


def detect_fresh_triangle_breakout(chart: PnFChart) -> PatternMatch | None:
    """The bullish_triangle signal fired on the most recent X column.

    Captures the transition state: a stock that just broke out of a triangle
    is in Section B for a brief window while the move develops.
    """
    signals = detect_signals(chart)
    if not signals:
        return None
    most_recent = signals[-1]
    if most_recent.type != "bullish_triangle":
        return None
    return PatternMatch(
        pattern_type="fresh_triangle_breakout",
        detected_date=most_recent.fired_date,
        description=f"Bullish triangle breakout at {most_recent.price_level}",
        strength=1.0,
    )


# ---------------------------------------------------------------------------
# 5. Catapult confirmed
# ---------------------------------------------------------------------------


def detect_catapult_confirmed(chart: PnFChart) -> PatternMatch | None:
    """The bullish_catapult signal fired on the most recent X column."""
    signals = detect_signals(chart)
    if not signals:
        return None
    most_recent = signals[-1]
    if most_recent.type != "bullish_catapult":
        return None
    return PatternMatch(
        pattern_type="catapult_confirmed",
        detected_date=most_recent.fired_date,
        description=f"Bullish catapult confirmed at {most_recent.price_level}",
        strength=1.0,
    )


# ---------------------------------------------------------------------------
# 6. RS strengthening on already-positive chart
# ---------------------------------------------------------------------------


def detect_rs_strengthening_on_positive(
    price_chart: PnFChart, rs_chart: PnFChart
) -> PatternMatch | None:
    """Price chart is on a buy signal AND the RS chart's most recent
    signal is also a buy AND the RS buy is recent (within the last
    3 columns of the RS chart).

    Captures the case where a stock that was already strong has
    suddenly started outperforming its peers — institutional flows
    accelerating.
    """
    sig = latest_signal(price_chart)
    if sig is None or not sig.is_bullish:
        return None
    rs_signals = detect_signals(rs_chart)
    if not rs_signals:
        return None
    most_recent_rs = rs_signals[-1]
    if not most_recent_rs.is_bullish:
        return None
    rs_columns_since = len(rs_chart.columns) - 1 - most_recent_rs.column_index
    if rs_columns_since > 3:
        return None
    return PatternMatch(
        pattern_type="rs_strengthening_on_positive",
        detected_date=most_recent_rs.fired_date,
        description=(
            f"Price on {sig.type}; RS {most_recent_rs.type} fired "
            f"{rs_columns_since} RS-column(s) ago"
        ),
        strength=0.9,
    )
