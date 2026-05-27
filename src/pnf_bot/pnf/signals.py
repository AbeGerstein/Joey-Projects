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
    "quadruple_top",
    "quintuple_top",
    "spread_triple_top",
    "spread_triple_bottom",
    "spread_quadruple_top",
    "spread_quintuple_top",
    # Compound signals
    "bullish_catapult",
    "bearish_catapult",
    "bullish_triangle",
    "bearish_triangle",
    "long_tail_down",
    "long_tail_up",
    "shakeout",
    "bearish_signal_reversal",
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

# Triangle detection — minimum number of prior X columns (or O columns)
# that must show the converging coil pattern before the breakout column.
# Three prior X cols plus two prior O cols = 5 prior columns of coil.
DEFAULT_TRIANGLE_MIN_X_PRIORS = 3

# Long tail threshold — number of boxes in a single column for it to
# qualify as a capitulation pattern. Dorsey commonly uses 17 boxes.
DEFAULT_LONG_TAIL_BOXES = 17


def detect_signals(
    chart: PnFChart,
    spread_tolerance_boxes: int = DEFAULT_SPREAD_TOLERANCE_BOXES,
    triangle_min_x_priors: int = DEFAULT_TRIANGLE_MIN_X_PRIORS,
    long_tail_boxes: int = DEFAULT_LONG_TAIL_BOXES,
) -> list[Signal]:
    """Walk the chart's columns and return every signal that fired.

    Signals are returned in chronological order. A single column may produce
    multiple signals (e.g., the same X column may register both a DT and a
    bullish catapult if it follows a triple-top column).
    """
    signals: list[Signal] = []
    for i, column in enumerate(chart.columns):
        if column.type == "X":
            signals.extend(_detect_x_signals(chart, i, spread_tolerance_boxes))
            signals.extend(_detect_bullish_compound_signals(
                chart, i, triangle_min_x_priors, long_tail_boxes
            ))
        else:
            signals.extend(_detect_o_signals(chart, i, spread_tolerance_boxes))
            signals.extend(_detect_bearish_compound_signals(
                chart, i, triangle_min_x_priors, long_tail_boxes
            ))
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

    # --- Quadruple Top: three prior X columns at the SAME top, current exceeds ---
    if len(prior_x_cols) >= 3:
        priors = prior_x_cols[:3]
        if priors[0].top == priors[1].top == priors[2].top:
            signal_level = priors[0].top + box
            if current.top >= signal_level:
                fired = current.date_when_extreme_reached(signal_level) or current.end_date
                signals.append(
                    Signal(
                        type="quadruple_top",
                        direction="bullish",
                        column_index=current_idx,
                        fired_date=fired,
                        price_level=signal_level,
                    )
                )

    # --- Quintuple Top: four prior X columns at the SAME top, current exceeds ---
    if len(prior_x_cols) >= 4:
        priors = prior_x_cols[:4]
        if priors[0].top == priors[1].top == priors[2].top == priors[3].top:
            signal_level = priors[0].top + box
            if current.top >= signal_level:
                fired = current.date_when_extreme_reached(signal_level) or current.end_date
                signals.append(
                    Signal(
                        type="quintuple_top",
                        direction="bullish",
                        column_index=current_idx,
                        fired_date=fired,
                        price_level=signal_level,
                    )
                )

    # --- Spread Quadruple Top: three prior X cols at SIMILAR tops within tolerance ---
    if len(prior_x_cols) >= 3:
        priors = prior_x_cols[:3]
        prior_tops = [p.top for p in priors]
        # Exclude exact-match case (that's the regular Quadruple Top)
        if len(set(prior_tops)) > 1:
            spread = max(prior_tops) - min(prior_tops)
            spread_boxes = spread / box
            if spread_boxes <= Decimal(spread_tolerance_boxes):
                signal_level = max(prior_tops) + box
                if current.top >= signal_level:
                    fired = (
                        current.date_when_extreme_reached(signal_level) or current.end_date
                    )
                    signals.append(
                        Signal(
                            type="spread_quadruple_top",
                            direction="bullish",
                            column_index=current_idx,
                            fired_date=fired,
                            price_level=signal_level,
                        )
                    )

    # --- Spread Quintuple Top: four prior X cols at SIMILAR tops within tolerance ---
    if len(prior_x_cols) >= 4:
        priors = prior_x_cols[:4]
        prior_tops = [p.top for p in priors]
        if len(set(prior_tops)) > 1:
            spread = max(prior_tops) - min(prior_tops)
            spread_boxes = spread / box
            if spread_boxes <= Decimal(spread_tolerance_boxes):
                signal_level = max(prior_tops) + box
                if current.top >= signal_level:
                    fired = (
                        current.date_when_extreme_reached(signal_level) or current.end_date
                    )
                    signals.append(
                        Signal(
                            type="spread_quintuple_top",
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

    Walks all columns before `current_idx` and filters by type. The result
    is ordered newest-first.

    Note: columns alternate X/O, so the same-type priors are at indices
    current_idx - 2, current_idx - 4, ... but we filter explicitly rather
    than relying on parity so this function works whether `column_type`
    matches the current column or not.
    """
    result: list[Column] = []
    for i in range(current_idx - 1, -1, -1):
        if columns[i].type == column_type:
            result.append(columns[i])
    return result


# ---------------------------------------------------------------------------
# Compound signal detectors (Phase 2C)
# ---------------------------------------------------------------------------


def _detect_bullish_compound_signals(
    chart: PnFChart,
    current_idx: int,
    triangle_min_x_priors: int,
    long_tail_boxes: int,
) -> list[Signal]:
    """Detect catapult, triangle, and long-tail-down signals on an X column."""
    current = chart.columns[current_idx]
    if current.type != "X":
        return []
    signals: list[Signal] = []
    box = current.box_size
    prior_x_cols = _prior_columns_of_type(chart.columns, current_idx, "X")

    # --- Bullish catapult: TT in column i-2, then DT in column i ---
    # Structural condition: column i-2 fired a TT, and column i exceeds it.
    if len(prior_x_cols) >= 3:
        x_minus_2 = prior_x_cols[0]
        x_minus_4 = prior_x_cols[1]
        x_minus_6 = prior_x_cols[2]
        # column i-2 fired TT means: top(i-2) > top(i-4) and top(i-4) == top(i-6)
        if (
            x_minus_2.top > x_minus_4.top
            and x_minus_4.top == x_minus_6.top
        ):
            signal_level = x_minus_2.top + box
            if current.top >= signal_level:
                fired = (
                    current.date_when_extreme_reached(signal_level) or current.end_date
                )
                signals.append(
                    Signal(
                        type="bullish_catapult",
                        direction="bullish",
                        column_index=current_idx,
                        fired_date=fired,
                        price_level=signal_level,
                    )
                )

    # --- Bullish triangle: converging coil broken by DT ---
    # Need triangle_min_x_priors X columns with strictly decreasing tops AND
    # the corresponding O columns having strictly increasing bottoms.
    if len(prior_x_cols) >= triangle_min_x_priors:
        coil_x = prior_x_cols[:triangle_min_x_priors]
        # Tops must be strictly decreasing as we go further back? No — we walk
        # prior_x_cols which is reverse chronological. coil_x[0] is most recent X.
        # Triangle pattern: as time progresses (older → newer), X tops decrease,
        # O bottoms rise. Reverse chronological view: coil_x[0] = newest = lowest,
        # coil_x[-1] = oldest = highest. So coil_x should be strictly increasing
        # when read in REVERSE order, i.e., tops decrease as we go forward in time.
        tops_in_chronological = [c.top for c in reversed(coil_x)]
        if all(
            tops_in_chronological[i] > tops_in_chronological[i + 1]
            for i in range(len(tops_in_chronological) - 1)
        ):
            # Now check the O columns between these X columns have rising bottoms
            prior_o_cols = _prior_columns_of_type(chart.columns, current_idx, "O")
            # We need triangle_min_x_priors - 1 prior O columns between the X cols
            n_o_needed = triangle_min_x_priors - 1
            if len(prior_o_cols) >= n_o_needed:
                coil_o = prior_o_cols[:n_o_needed]
                bottoms_in_chronological = [c.bottom for c in reversed(coil_o)]
                if all(
                    bottoms_in_chronological[i] < bottoms_in_chronological[i + 1]
                    for i in range(len(bottoms_in_chronological) - 1)
                ):
                    # Triangle is coiling. Current column must fire a DT to confirm breakout.
                    immediate_prior_x = coil_x[0]
                    signal_level = immediate_prior_x.top + box
                    if current.top >= signal_level:
                        fired = (
                            current.date_when_extreme_reached(signal_level)
                            or current.end_date
                        )
                        signals.append(
                            Signal(
                                type="bullish_triangle",
                                direction="bullish",
                                column_index=current_idx,
                                fired_date=fired,
                                price_level=signal_level,
                            )
                        )

    # --- Long tail down → bullish reversal signal ---
    # The X column at i forms after an O column at i-1 with height >= long_tail_boxes.
    if current_idx >= 1:
        prior = chart.columns[current_idx - 1]
        if prior.type == "O" and prior.height_boxes >= long_tail_boxes:
            signals.append(
                Signal(
                    type="long_tail_down",
                    direction="bullish",
                    column_index=current_idx,
                    fired_date=current.start_date,
                    price_level=current.bottom,
                )
            )

    # --- Shakeout (BULLISH): tight pullback within a bullish chart that reclaims highs ---
    # Pattern: prior O column (col i-1) made a SHALLOW dip below the X col before it
    # (1-3 boxes lower than the X col's bottom), and the current X column fires a
    # Double Top reclaiming new highs. The brief dip "shakes out" weak hands; the
    # prompt new buy signal confirms the uptrend is intact.
    if current_idx >= 2:
        prior_o = chart.columns[current_idx - 1]
        x_before_o = chart.columns[current_idx - 2]
        if prior_o.type == "O" and x_before_o.type == "X":
            dip_boxes = (x_before_o.bottom - prior_o.bottom) / box
            shallow = Decimal("1") <= dip_boxes <= Decimal("3")
            dt_level = x_before_o.top + box
            fired_dt = current.top >= dt_level
            if shallow and fired_dt:
                fired = current.date_when_extreme_reached(dt_level) or current.end_date
                signals.append(
                    Signal(
                        type="shakeout",
                        direction="bullish",
                        column_index=current_idx,
                        fired_date=fired,
                        price_level=dt_level,
                    )
                )

    # --- Bearish Signal Reversal (BULLISH despite the name) ---
    # A buy signal fires immediately after the prior O column fired a sell signal.
    # In Dorsey's framework this signals that the bears who just shorted the sell
    # are getting reversed out — often the start of a durable trend change.
    # Structural: prior O col i-1 fired a Double Bottom (broke prior O col's low),
    # current X col i fires a Double Top (exceeds prior X col's top).
    if current_idx >= 3:
        prior_o = chart.columns[current_idx - 1]
        x_before_o = chart.columns[current_idx - 2]
        o_before_x = chart.columns[current_idx - 3]
        if (
            prior_o.type == "O"
            and x_before_o.type == "X"
            and o_before_x.type == "O"
        ):
            prior_o_fired_db = prior_o.bottom < o_before_x.bottom
            dt_level = x_before_o.top + box
            current_fired_dt = current.top >= dt_level
            if prior_o_fired_db and current_fired_dt:
                fired = current.date_when_extreme_reached(dt_level) or current.end_date
                signals.append(
                    Signal(
                        type="bearish_signal_reversal",
                        direction="bullish",
                        column_index=current_idx,
                        fired_date=fired,
                        price_level=dt_level,
                    )
                )

    return signals


def _detect_bearish_compound_signals(
    chart: PnFChart,
    current_idx: int,
    triangle_min_x_priors: int,
    long_tail_boxes: int,
) -> list[Signal]:
    """Detect bearish catapult, bearish triangle, and long-tail-up signals on an O column."""
    current = chart.columns[current_idx]
    if current.type != "O":
        return []
    signals: list[Signal] = []
    box = current.box_size
    prior_o_cols = _prior_columns_of_type(chart.columns, current_idx, "O")

    # --- Bearish catapult: TB in column i-2, then DB in column i ---
    if len(prior_o_cols) >= 3:
        o_minus_2 = prior_o_cols[0]
        o_minus_4 = prior_o_cols[1]
        o_minus_6 = prior_o_cols[2]
        if (
            o_minus_2.bottom < o_minus_4.bottom
            and o_minus_4.bottom == o_minus_6.bottom
        ):
            signal_level = o_minus_2.bottom - box
            if current.bottom <= signal_level:
                fired = (
                    current.date_when_extreme_reached(signal_level) or current.end_date
                )
                signals.append(
                    Signal(
                        type="bearish_catapult",
                        direction="bearish",
                        column_index=current_idx,
                        fired_date=fired,
                        price_level=signal_level,
                    )
                )

    # --- Bearish triangle: converging coil broken by DB ---
    if len(prior_o_cols) >= triangle_min_x_priors:
        coil_o = prior_o_cols[:triangle_min_x_priors]
        # Bottoms must rise as we go forward in time (chart converges)
        bottoms_in_chronological = [c.bottom for c in reversed(coil_o)]
        if all(
            bottoms_in_chronological[i] < bottoms_in_chronological[i + 1]
            for i in range(len(bottoms_in_chronological) - 1)
        ):
            prior_x_cols = _prior_columns_of_type(chart.columns, current_idx, "X")
            n_x_needed = triangle_min_x_priors - 1
            if len(prior_x_cols) >= n_x_needed:
                coil_x = prior_x_cols[:n_x_needed]
                # X tops must fall as we go forward in time
                tops_in_chronological = [c.top for c in reversed(coil_x)]
                if all(
                    tops_in_chronological[i] > tops_in_chronological[i + 1]
                    for i in range(len(tops_in_chronological) - 1)
                ):
                    immediate_prior_o = coil_o[0]
                    signal_level = immediate_prior_o.bottom - box
                    if current.bottom <= signal_level:
                        fired = (
                            current.date_when_extreme_reached(signal_level)
                            or current.end_date
                        )
                        signals.append(
                            Signal(
                                type="bearish_triangle",
                                direction="bearish",
                                column_index=current_idx,
                                fired_date=fired,
                                price_level=signal_level,
                            )
                        )

    # --- Long tail up → bearish reversal signal ---
    # The O column at i forms after an X column at i-1 with height >= long_tail_boxes.
    if current_idx >= 1:
        prior = chart.columns[current_idx - 1]
        if prior.type == "X" and prior.height_boxes >= long_tail_boxes:
            signals.append(
                Signal(
                    type="long_tail_up",
                    direction="bearish",
                    column_index=current_idx,
                    fired_date=current.start_date,
                    price_level=current.top,
                )
            )

    return signals
