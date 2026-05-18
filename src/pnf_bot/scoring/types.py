"""Shared types for the scoring layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PatternMatch:
    """A pattern detected on a single stock at a specific evaluation date.

    Used for both pre-momentum and in-momentum pattern detection. The
    `pattern_type` string identifies which pattern matched — by convention
    it matches one of the PreMomentumPatternType or InMomentumPatternType
    literal values.

    `strength` (0.0–1.0) captures how strongly the pattern matched. For
    binary patterns (long_tail_reversal — either there or not) this is
    1.0 when matched. For graded patterns (bullish_triangle_near_breakout,
    where being 1 box from breakout is stronger than being 3 boxes away)
    strength varies smoothly.

    `detected_date` is the date on which the pattern became active. For
    fresh patterns (just-fired-last-night), this is the most recent
    trading day. For older patterns still in effect, it's earlier.
    """

    pattern_type: str
    detected_date: date
    description: str
    strength: float = 1.0
