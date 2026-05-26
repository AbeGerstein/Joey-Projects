"""Pre-momentum pattern detectors.

Implements the 7 patterns from docs/methodology/pre-momentum-detection.md.
Each detector takes the chart objects the P&F engine produces and returns
a PatternMatch if the pattern is currently active on the stock.

Patterns:
1. Bullish triangle near breakout
2. Long tail down reversal + initial buy signal
3. First buy signal after extended sell regime
4. Bullish catapult setup forming
5. Long-term RS turning positive
6. Sector BPI inflection from below 30%
7. Sideways base with rising RS underneath

Aggregated via `detect_pre_momentum_patterns(...)` — call once per stock,
get all matching patterns.

These detectors look at CURRENT chart state (is this pattern active now?)
rather than firing on a specific event. The bot calls them daily; a stock
that matches one or more patterns becomes a Section A candidate.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pnf_bot.pnf.signals import detect_signals, latest_signal
from pnf_bot.pnf.types import PnFChart
from pnf_bot.scoring.types import PatternMatch

PreMomentumPatternType = Literal[
    "bullish_triangle_near_breakout",
    "long_tail_reversal",
    "first_buy_after_long_sell",
    "bullish_catapult_forming",
    "rs_turning_positive",
    "sector_bpi_inflection",
    "sideways_base_rising_rs",
]


# Configuration defaults — tunable in Phase 4 backtest
DEFAULT_TRIANGLE_NEAR_BREAKOUT_BOXES = 3
DEFAULT_LONG_TAIL_BOXES = 17
DEFAULT_MIN_SELL_REGIME_DAYS = 180  # ~6 months
DEFAULT_SECTOR_BPI_INFLECTION_LOOKBACK = 5  # columns
DEFAULT_SIDEWAYS_BASE_COLUMNS = 6
DEFAULT_SIDEWAYS_BASE_RANGE_PCT = Decimal("0.15")  # 15%
DEFAULT_BPI_OVERSOLD_THRESHOLD = Decimal("30")


def detect_pre_momentum_patterns(
    price_chart: PnFChart,
    rs_chart: PnFChart | None = None,
    sector_bpi_chart: PnFChart | None = None,
    as_of_date: date | None = None,
) -> list[PatternMatch]:
    """Run all 7 pre-momentum detectors. Returns every pattern currently active.

    `rs_chart` and `sector_bpi_chart` are optional; detectors that require
    them are skipped when absent. The price chart is required.
    """
    matches: list[PatternMatch] = []

    triangle = detect_bullish_triangle_near_breakout(price_chart)
    if triangle:
        matches.append(triangle)

    long_tail = detect_long_tail_reversal(price_chart)
    if long_tail:
        matches.append(long_tail)

    first_buy = detect_first_buy_after_long_sell(price_chart)
    if first_buy:
        matches.append(first_buy)

    catapult = detect_bullish_catapult_forming(price_chart)
    if catapult:
        matches.append(catapult)

    if rs_chart is not None:
        rs_turn = detect_rs_turning_positive(rs_chart)
        if rs_turn:
            matches.append(rs_turn)

        if price_chart is not None:
            sideways = detect_sideways_base_with_rising_rs(price_chart, rs_chart)
            if sideways:
                matches.append(sideways)

    if sector_bpi_chart is not None:
        bpi_inflection = detect_sector_bpi_inflection(sector_bpi_chart)
        if bpi_inflection:
            matches.append(bpi_inflection)

    return matches


# ---------------------------------------------------------------------------
# 1. Bullish triangle near breakout
# ---------------------------------------------------------------------------


def detect_bullish_triangle_near_breakout(
    chart: PnFChart,
    max_boxes_to_breakout: int = DEFAULT_TRIANGLE_NEAR_BREAKOUT_BOXES,
) -> PatternMatch | None:
    """Detect a coiling bullish triangle where current price is near (but has not
    yet crossed) the breakout level.

    The coil structure: declining X tops AND rising O bottoms across recent
    columns. The breakout level is one box above the most recent X column's
    top. Match if current column's top is within `max_boxes_to_breakout`
    of that level but does not exceed it.
    """
    cols = chart.columns
    if len(cols) < 5:
        return None

    x_cols = [c for c in cols if c.type == "X"]
    o_cols = [c for c in cols if c.type == "O"]
    if len(x_cols) < 3 or len(o_cols) < 2:
        return None

    # Last 3 X columns must show declining tops
    recent_x = x_cols[-3:]
    if not all(recent_x[i].top > recent_x[i + 1].top for i in range(len(recent_x) - 1)):
        return None

    # Last 2 O columns must show rising bottoms
    recent_o = o_cols[-2:]
    if not all(recent_o[i].bottom < recent_o[i + 1].bottom for i in range(len(recent_o) - 1)):
        return None

    current = cols[-1]
    box = current.box_size
    # Breakout level = most recent (immediate prior) X column top + box
    # If current is X, the immediate prior X is recent_x[-2]; if current is O, it's recent_x[-1]
    if current.type == "X":
        if len(recent_x) < 2:
            return None
        prior_x_top = recent_x[-2].top
    else:
        prior_x_top = recent_x[-1].top

    breakout_level = prior_x_top + box
    boxes_remaining = int((breakout_level - current.top) / box)

    # Must be approaching from below — not already past it
    if current.top >= breakout_level:
        return None
    if boxes_remaining > max_boxes_to_breakout:
        return None

    # Strength: closer to breakout = stronger (1.0 at 1 box, 0.5 at max)
    strength = max(0.5, 1.0 - (boxes_remaining - 1) / max(1, max_boxes_to_breakout))

    return PatternMatch(
        pattern_type="bullish_triangle_near_breakout",
        detected_date=current.end_date,
        description=(
            f"Triangle coil; current top {current.top} is {boxes_remaining} box(es) "
            f"below breakout level {breakout_level}"
        ),
        strength=strength,
    )


# ---------------------------------------------------------------------------
# 2. Long tail down reversal + initial buy signal
# ---------------------------------------------------------------------------


def detect_long_tail_reversal(
    chart: PnFChart, long_tail_boxes: int = DEFAULT_LONG_TAIL_BOXES
) -> PatternMatch | None:
    """An X column has just formed after an O column of ≥ long_tail_boxes.

    Captures the capitulation-then-reversal setup at a multi-month low.
    """
    cols = chart.columns
    if len(cols) < 2:
        return None
    prev = cols[-2]
    current = cols[-1]
    if prev.type != "O" or current.type != "X":
        return None
    if prev.height_boxes < long_tail_boxes:
        return None

    # Strength: longer the O column, stronger the signal
    strength = min(1.0, prev.height_boxes / (long_tail_boxes * 1.5))
    return PatternMatch(
        pattern_type="long_tail_reversal",
        detected_date=current.start_date,
        description=(
            f"Long-tail O column of {prev.height_boxes} boxes followed by X reversal"
        ),
        strength=strength,
    )


# ---------------------------------------------------------------------------
# 3. First buy signal after extended sell regime
# ---------------------------------------------------------------------------


def detect_first_buy_after_long_sell(
    chart: PnFChart, min_sell_regime_days: int = DEFAULT_MIN_SELL_REGIME_DAYS
) -> PatternMatch | None:
    """The chart's most recent signal is a buy, and the prior signal was a
    sell that persisted for ≥ min_sell_regime_days.

    The very first buy after an extended sell regime is statistically among
    the most reliable signals in P&F. Captures the regime change.
    """
    signals = detect_signals(chart)
    if len(signals) < 2:
        return None

    # Find the most recent buy and the most recent sell before it
    bullish_signals = [s for s in signals if s.is_bullish]
    bearish_signals = [s for s in signals if s.is_bearish]
    if not bullish_signals or not bearish_signals:
        return None

    most_recent_buy = bullish_signals[-1]
    # The most recent sell BEFORE the most recent buy
    sells_before_buy = [s for s in bearish_signals if s.fired_date < most_recent_buy.fired_date]
    if not sells_before_buy:
        return None
    most_recent_sell = sells_before_buy[-1]

    # No intervening buys
    intervening_buys = [
        s
        for s in bullish_signals
        if most_recent_sell.fired_date < s.fired_date < most_recent_buy.fired_date
    ]
    if intervening_buys:
        return None

    gap_days = (most_recent_buy.fired_date - most_recent_sell.fired_date).days
    if gap_days < min_sell_regime_days:
        return None

    strength = min(1.0, gap_days / (min_sell_regime_days * 2))
    return PatternMatch(
        pattern_type="first_buy_after_long_sell",
        detected_date=most_recent_buy.fired_date,
        description=(
            f"First buy signal ({most_recent_buy.type}) after a {gap_days}-day sell regime"
        ),
        strength=strength,
    )


# ---------------------------------------------------------------------------
# 4. Bullish catapult setup forming (not yet fired)
# ---------------------------------------------------------------------------


def detect_bullish_catapult_forming(chart: PnFChart) -> PatternMatch | None:
    """A triple-top pattern recently fired, the pullback is in progress or
    just completed, and the catapult breakout has NOT yet fired.

    Differs from the bullish_catapult signal (which fires on the breakout
    confirmation) — this detects the setup in the pre-breakout phase, so
    we surface the candidate before the move begins.
    """
    cols = chart.columns
    if len(cols) < 4:
        return None

    # The structural pattern (TT-then-pullback) can still match while the
    # chart is in active breakdown — the post-TT O column may have gone deep
    # enough to fire fresh SELL signals. Reject those cases up front: a
    # genuine pre-catapult chart never has a bearish signal as its most
    # recent event.
    most_recent = latest_signal(chart)
    if most_recent is not None and most_recent.is_bearish:
        return None

    # Look for a recent TT structurally — need 3 X cols with the most recent
    # exceeding the prior two at equal tops
    x_cols = [(i, c) for i, c in enumerate(cols) if c.type == "X"]
    if len(x_cols) < 3:
        return None

    # The TT could be in column k where the next column k+1 is the pullback O
    # and the current column is either still the O (pullback in progress) or
    # a new X column that hasn't yet exceeded column k's top.
    for tt_idx, tt_col in reversed(x_cols[:-1]):
        # tt_col must be the breakout that fired TT: top(tt_col) > top(prior X) AND prior X tops equal
        priors = [c for i, c in x_cols if i < tt_idx]
        if len(priors) < 2:
            continue
        if priors[-1].top == priors[-2].top and tt_col.top > priors[-1].top:
            # TT structurally fired at tt_idx. Check the state after.
            cols_after = cols[tt_idx + 1 :]
            if not cols_after:
                continue
            # First column after TT must be O (the pullback)
            if cols_after[0].type != "O":
                continue
            # Final state: current column is either the pullback O still, OR a new X
            # that hasn't yet exceeded tt_col.top
            current = cols[-1]
            if current.type == "O":
                # Still in pullback phase
                return PatternMatch(
                    pattern_type="bullish_catapult_forming",
                    detected_date=current.end_date,
                    description=(
                        f"Catapult setup: triple top at {tt_col.top} fired; "
                        f"pullback in progress"
                    ),
                    strength=0.7,
                )
            if current.type == "X" and current.top <= tt_col.top:
                # New X column forming but hasn't broken out yet
                return PatternMatch(
                    pattern_type="bullish_catapult_forming",
                    detected_date=current.end_date,
                    description=(
                        f"Catapult setup: triple top at {tt_col.top} fired, pullback "
                        f"completed, new X column forming"
                    ),
                    strength=0.9,
                )
            # If current X has already broken out, the catapult signal itself fires,
            # not the pre-momentum version
            return None

    return None


# ---------------------------------------------------------------------------
# 5. Long-term RS turning positive
# ---------------------------------------------------------------------------


def detect_rs_turning_positive(
    rs_chart: PnFChart, min_sell_regime_days: int = DEFAULT_MIN_SELL_REGIME_DAYS
) -> PatternMatch | None:
    """The RS chart fired its first buy signal after an extended sell regime.

    Same pattern definition as `detect_first_buy_after_long_sell` but applied
    to the RS chart instead of the price chart.
    """
    match = detect_first_buy_after_long_sell(rs_chart, min_sell_regime_days)
    if match is None:
        return None
    # Rename the pattern type
    return PatternMatch(
        pattern_type="rs_turning_positive",
        detected_date=match.detected_date,
        description=f"RS regime change: {match.description}",
        strength=match.strength,
    )


# ---------------------------------------------------------------------------
# 6. Sector BPI inflection from below 30%
# ---------------------------------------------------------------------------


def detect_sector_bpi_inflection(
    sector_bpi_chart: PnFChart,
    oversold_threshold: Decimal = DEFAULT_BPI_OVERSOLD_THRESHOLD,
    lookback_columns: int = DEFAULT_SECTOR_BPI_INFLECTION_LOOKBACK,
) -> PatternMatch | None:
    """The sector BPI was below 30% recently and has reversed up into an X column.

    Captures sectors emerging from oversold conditions — a common
    pre-momentum tailwind for leading stocks in that sector.
    """
    cols = sector_bpi_chart.columns
    if not cols:
        return None
    current = cols[-1]
    if current.type != "X":
        return None

    # Check recent columns for a bottom below the oversold threshold
    recent = cols[-lookback_columns:] if len(cols) > lookback_columns else cols
    recent_low = min(c.bottom for c in recent)
    if recent_low >= oversold_threshold:
        return None

    return PatternMatch(
        pattern_type="sector_bpi_inflection",
        detected_date=current.start_date,
        description=(
            f"Sector BPI inflection: recent low {recent_low}% (below {oversold_threshold}%), "
            f"now reversing up"
        ),
        strength=1.0,
    )


# ---------------------------------------------------------------------------
# 7. Sideways base with rising RS underneath
# ---------------------------------------------------------------------------


def detect_sideways_base_with_rising_rs(
    price_chart: PnFChart,
    rs_chart: PnFChart,
    base_columns: int = DEFAULT_SIDEWAYS_BASE_COLUMNS,
    range_pct: Decimal = DEFAULT_SIDEWAYS_BASE_RANGE_PCT,
) -> PatternMatch | None:
    """Price chart is in a narrow sideways range over the last `base_columns`,
    while the RS chart is currently in a positive regime.

    Captures the "RS leads price" pattern — improving relative strength under
    a basing price chart often precedes a breakout.
    """
    cols = price_chart.columns
    if len(cols) < base_columns:
        return None

    base = cols[-base_columns:]
    top = max(c.top for c in base)
    bottom = min(c.bottom for c in base)
    midpoint = (top + bottom) / Decimal("2")
    if midpoint <= Decimal("0"):
        return None
    range_fraction = (top - bottom) / midpoint
    if range_fraction > range_pct:
        return None

    # RS chart must be on a buy signal currently
    rs_signals = detect_signals(rs_chart)
    if not rs_signals or not rs_signals[-1].is_bullish:
        return None

    return PatternMatch(
        pattern_type="sideways_base_rising_rs",
        detected_date=base[-1].end_date,
        description=(
            f"Price base ({base_columns} columns, range {range_fraction:.1%}) "
            f"with RS chart in positive regime"
        ),
        strength=0.9,
    )
