"""Anti-pattern (exhaustion) detectors.

Implements the exclusion criteria from docs/methodology/in-momentum-detection.md.
A stock matching any anti-pattern is past the point of responsible entry
and should be EXCLUDED from Section B (and never appear in Section A).

Anti-patterns:
1. Parabolic X column (single X column >= 15-20 boxes — high implied vol,
   wide stop required, statistically poor forward returns)
2. Extended above bullish support (more than ~15 boxes above the trendline)
3. Blow-off characteristics (price >50% above a long-term moving-average
   analog of the chart)
4. Recent break of bullish support (the support line was JUST broken —
   even if other signals look strong, momentum is faltering)

Aggregated via `is_exhausted(chart)` which returns True if any exhaustion
criterion is met.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pnf_bot.pnf.trendlines import (
    boxes_above_bullish_support,
    find_bullish_support_line,
    is_above_bullish_support,
)
from pnf_bot.pnf.types import PnFChart


@dataclass(frozen=True)
class ExhaustionReason:
    """A single anti-pattern triggered on a chart."""

    code: str  # one of "parabolic", "extended_above_support", "blow_off", "support_broken"
    description: str


# Configuration defaults
DEFAULT_PARABOLIC_MIN_BOXES = 18
DEFAULT_MAX_BOXES_ABOVE_SUPPORT = 15
DEFAULT_BLOW_OFF_MULTIPLIER = Decimal("1.5")  # 50% above the chart midpoint
DEFAULT_BLOW_OFF_LOOKBACK_COLUMNS = 48  # ~2 years of columns for the analog


def evaluate_anti_patterns(
    chart: PnFChart,
    parabolic_min_boxes: int = DEFAULT_PARABOLIC_MIN_BOXES,
    max_boxes_above_support: int = DEFAULT_MAX_BOXES_ABOVE_SUPPORT,
    blow_off_multiplier: Decimal = DEFAULT_BLOW_OFF_MULTIPLIER,
    blow_off_lookback: int = DEFAULT_BLOW_OFF_LOOKBACK_COLUMNS,
) -> list[ExhaustionReason]:
    """Return every anti-pattern that triggered on this chart.

    An empty list means the chart is clean — no exhaustion concerns.
    """
    reasons: list[ExhaustionReason] = []

    if _is_parabolic(chart, parabolic_min_boxes):
        cur = chart.columns[-1]
        reasons.append(
            ExhaustionReason(
                code="parabolic",
                description=(
                    f"Current {cur.type} column is {cur.height_boxes} boxes "
                    f"(threshold {parabolic_min_boxes}) — parabolic"
                ),
            )
        )

    if _is_extended_above_support(chart, max_boxes_above_support):
        boxes = boxes_above_bullish_support(chart)
        reasons.append(
            ExhaustionReason(
                code="extended_above_support",
                description=(
                    f"Current X is {boxes} boxes above bullish support "
                    f"(threshold {max_boxes_above_support})"
                ),
            )
        )

    if _has_blow_off_characteristics(chart, blow_off_multiplier, blow_off_lookback):
        reasons.append(
            ExhaustionReason(
                code="blow_off",
                description=(
                    f"Current price > {(blow_off_multiplier - 1) * 100:.0f}% "
                    f"above {blow_off_lookback}-column midpoint analog"
                ),
            )
        )

    if _support_recently_broken(chart):
        reasons.append(
            ExhaustionReason(
                code="support_broken",
                description="Bullish support trendline has been broken by a recent O column",
            )
        )

    return reasons


def is_exhausted(chart: PnFChart, **kwargs) -> bool:  # noqa: ANN003
    """Convenience: True if any anti-pattern triggered. kwargs forwarded to evaluate."""
    return len(evaluate_anti_patterns(chart, **kwargs)) > 0


# ---------------------------------------------------------------------------
# Individual anti-pattern checks
# ---------------------------------------------------------------------------


def _is_parabolic(chart: PnFChart, min_boxes: int) -> bool:
    """True if the most recent X column has >= min_boxes boxes without reversal."""
    cols = chart.columns
    if not cols:
        return False
    current = cols[-1]
    if current.type != "X":
        return False
    return current.height_boxes >= min_boxes


def _is_extended_above_support(chart: PnFChart, max_boxes: int) -> bool:
    """True if the most recent X column is far above the bullish support line."""
    if not chart.columns:
        return False
    boxes = boxes_above_bullish_support(chart)
    return boxes > max_boxes


def _has_blow_off_characteristics(
    chart: PnFChart, multiplier: Decimal, lookback_columns: int
) -> bool:
    """True if current price is far above a long-term midpoint analog.

    Midpoint analog: average of the highest X top and lowest O bottom in
    the last `lookback_columns` columns. Approximates a long-term moving
    average without leaving the P&F coordinate space.
    """
    cols = chart.columns
    if len(cols) < lookback_columns // 2:
        return False  # Not enough history to make the call
    recent = cols[-lookback_columns:] if len(cols) > lookback_columns else cols
    x_tops = [c.top for c in recent if c.type == "X"]
    o_bottoms = [c.bottom for c in recent if c.type == "O"]
    if not x_tops or not o_bottoms:
        return False
    midpoint = (max(x_tops) + min(o_bottoms)) / Decimal("2")
    if midpoint <= Decimal("0"):
        return False
    current = cols[-1]
    current_level = current.top if current.type == "X" else current.bottom
    return current_level > midpoint * multiplier


def _support_recently_broken(chart: PnFChart) -> bool:
    """True if a bullish support line WAS drawable but is now broken.

    Note: is_above_bullish_support returns False if NO line exists OR if it's
    broken. We distinguish: if a line exists but is broken, that's a real
    exhaustion signal; if no line exists at all (insufficient history),
    that's not.
    """
    line = find_bullish_support_line(chart)
    if line is None:
        return False
    return not is_above_bullish_support(chart)
