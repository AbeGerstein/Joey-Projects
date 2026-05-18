"""Tests for anti-pattern (exhaustion) detectors."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

from pnf_bot.pnf import construct_chart
from pnf_bot.scoring.anti_patterns import (
    evaluate_anti_patterns,
    is_exhausted,
)


def _bars(start: date, hl: list[tuple[float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"open": (h + l) / 2, "high": h, "low": l, "close": (h + l) / 2, "volume": 1_000_000}
            for (h, l) in hl
        ],
        index=[start + timedelta(days=i) for i in range(len(hl))],
    )


class TestParabolic:
    def test_long_single_x_column_is_parabolic(self) -> None:
        """An X column of 20+ boxes with no reversal triggers parabolic."""
        # Single bar with a wide high reaching 75 from anchor 50 = 25-box X column
        bars = [
            (50.0, 50.0),
            (75.0, 50.0),
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        reasons = evaluate_anti_patterns(chart, parabolic_min_boxes=18)
        codes = [r.code for r in reasons]
        assert "parabolic" in codes
        assert is_exhausted(chart, parabolic_min_boxes=18) is True

    def test_short_x_column_not_parabolic(self) -> None:
        bars = [
            (50.0, 50.0),
            (55.0, 50.0),  # 5-box column
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        reasons = evaluate_anti_patterns(chart, parabolic_min_boxes=18)
        codes = [r.code for r in reasons]
        assert "parabolic" not in codes


class TestExtendedAboveSupport:
    def test_far_above_support_triggers(self) -> None:
        """A chart that has rallied far above its bullish support line."""
        # Build a chart with one early low and a strong sustained rally
        bars = [
            (50.0, 50.0),     # X1 anchor at 50
            (50.0, 45.0),     # O1 to 45 (only O column)
            (80.0, 45.0),     # X2 to 80 (35-box rally — far above support)
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        reasons = evaluate_anti_patterns(chart, max_boxes_above_support=15)
        codes = [r.code for r in reasons]
        # Should flag extended_above_support (X2 top 80 is ~33 boxes above support at 46)
        assert "extended_above_support" in codes


class TestBlowOff:
    def test_short_chart_no_blow_off(self) -> None:
        """A chart too short to compute a midpoint analog doesn't trigger blow-off."""
        bars = [
            (50.0, 50.0),
            (55.0, 50.0),
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        reasons = evaluate_anti_patterns(chart, blow_off_lookback=48)
        codes = [r.code for r in reasons]
        # Not enough history → blow_off should not fire
        assert "blow_off" not in codes


class TestSupportBroken:
    def test_clean_chart_no_break(self) -> None:
        bars = [
            (50.0, 50.0),
            (50.0, 45.0),
            (51.0, 45.0),
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        reasons = evaluate_anti_patterns(chart)
        codes = [r.code for r in reasons]
        # With one O column anchoring support, no subsequent O can have broken it
        assert "support_broken" not in codes


class TestExhaustionAggregate:
    def test_clean_chart_not_exhausted(self) -> None:
        bars = [
            (50.0, 50.0),
            (50.0, 47.0),
            (52.0, 47.0),
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        assert is_exhausted(chart) is False

    def test_parabolic_chart_is_exhausted(self) -> None:
        bars = [
            (50.0, 50.0),
            (75.0, 50.0),
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        assert is_exhausted(chart, parabolic_min_boxes=18) is True
