"""Tests for P&F chart construction from OHLC.

Each test constructs a synthetic OHLC DataFrame designed to exercise a
specific scenario in the chart construction algorithm, then verifies the
resulting chart matches expectations.

The tests use traditional scaling at the $20-$100 tier ($1 boxes) so the
math is easy to reason about.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from pnf_bot.pnf import (
    PercentageScaling,
    PnFChart,
    TraditionalScaling,
    construct_chart,
)


def _ohlc(bars: list[tuple[date, float, float]]) -> pd.DataFrame:
    """Build an OHLC DataFrame from a list of (date, high, low) tuples.

    Open and close are filled in halfway between high and low for completeness;
    the chart construction algorithm uses only high and low.
    """
    return pd.DataFrame(
        [
            {
                "open": (h + l) / 2,
                "high": h,
                "low": l,
                "close": (h + l) / 2,
                "volume": 1_000_000,
            }
            for (_, h, l) in bars
        ],
        index=[d for (d, _, _) in bars],
    )


def _d(s: str) -> Decimal:
    return Decimal(s)


# ---------------------------------------------------------------------------
# Bootstrap: first column from first bar
# ---------------------------------------------------------------------------


class TestInitialColumn:
    def test_first_bar_starts_an_x_column(self) -> None:
        """The first bar always starts an X column by convention."""
        bars = [(date(2026, 1, 5), 50.5, 50.0)]
        chart = construct_chart("TEST", _ohlc(bars))
        assert chart.column_count == 1
        assert chart.columns[0].type == "X"

    def test_first_column_uses_appropriate_box_size(self) -> None:
        """At $50, traditional scaling uses $1 boxes."""
        bars = [(date(2026, 1, 5), 50.0, 50.0)]
        chart = construct_chart("TEST", _ohlc(bars))
        assert chart.columns[0].box_size == _d("1.00")


# ---------------------------------------------------------------------------
# Extension within an X column
# ---------------------------------------------------------------------------


class TestXColumnExtension:
    def test_higher_high_extends_x_column(self) -> None:
        """Day 1: anchor at 50. Day 2: high 52 → extend to 52."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 52.0, 51.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        assert chart.column_count == 1
        assert chart.columns[0].top == _d("52.00")

    def test_extension_uses_fixed_box_size_for_column(self) -> None:
        """Box size at column start is locked, not re-evaluated as price moves up tiers.

        Start a column at $98 (box=$1 for $20-$100 tier). Extend through $105.
        Even though $105 would normally be the $2-box tier, the column's
        box size stays at $1.
        """
        bars = [
            (date(2026, 1, 5), 98.0, 98.0),
            (date(2026, 1, 6), 105.0, 99.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        # Column should extend up — box size frozen at $1
        assert chart.columns[0].box_size == _d("1.00")
        assert chart.columns[0].top == _d("105.00")

    def test_no_change_when_high_doesnt_reach_next_box(self) -> None:
        """If today's high doesn't reach the next-box level, no extension."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 50.5, 50.0),  # high < 51 (one box up from 50)
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        assert chart.columns[0].top == _d("50.00")
        assert chart.column_count == 1


# ---------------------------------------------------------------------------
# Reversal from X to O
# ---------------------------------------------------------------------------


class TestXToOReversal:
    def test_three_box_drop_triggers_reversal(self) -> None:
        """X column at top=55. Day 2: low 51 → 4 boxes below → reverse to O column.

        Reversal threshold = 55 - 3 = 52. Low of 51 is below threshold.
        """
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),
            (date(2026, 1, 6), 55.0, 51.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        assert chart.column_count == 2
        assert chart.columns[0].type == "X"
        assert chart.columns[1].type == "O"
        # New O column tops at one box below X top: 55 - 1 = 54
        assert chart.columns[1].top == _d("54.00")
        # And extends down to 51
        assert chart.columns[1].bottom == _d("51.00")

    def test_two_box_drop_does_not_reverse(self) -> None:
        """A drop of exactly 2 boxes is below the 3-box threshold; no reversal."""
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),
            (date(2026, 1, 6), 55.0, 53.0),  # drop 2 boxes only
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        assert chart.column_count == 1
        assert chart.columns[0].type == "X"

    def test_extension_takes_precedence_over_reversal(self) -> None:
        """If a bar can both extend up AND would otherwise reverse, extend wins.

        X at 55. Wide bar: high 56 (extends), low 50 (would reverse). Extension wins.
        """
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),
            (date(2026, 1, 6), 56.0, 50.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        assert chart.column_count == 1
        assert chart.columns[0].top == _d("56.00")


# ---------------------------------------------------------------------------
# Reversal from O to X
# ---------------------------------------------------------------------------


class TestOToXReversal:
    def test_three_box_rise_from_o_triggers_reversal(self) -> None:
        """X column → reverse to O at bottom 50 → 3-box rise → reverse to X."""
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),
            (date(2026, 1, 6), 55.0, 50.0),  # reverses X → O, O bottoms at 50
            (date(2026, 1, 7), 54.0, 51.0),  # rise of 4 boxes from bottom → reverse to X
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        # Should have 3 columns: X, O, X
        assert chart.column_count == 3
        assert chart.columns[0].type == "X"
        assert chart.columns[1].type == "O"
        assert chart.columns[2].type == "X"
        # New X column starts at one box above O bottom: 50 + 1 = 51
        assert chart.columns[2].bottom == _d("51.00")
        # And extends to today's high: 54
        assert chart.columns[2].top == _d("54.00")


# ---------------------------------------------------------------------------
# Multi-column scenarios
# ---------------------------------------------------------------------------


class TestMultiColumn:
    def test_long_uptrend_single_column(self) -> None:
        """A series of consecutively higher highs forms one long X column."""
        start = date(2026, 1, 5)
        bars = [(start + timedelta(days=i), 50.0 + i, 49.0 + i) for i in range(10)]
        chart = construct_chart("TEST", _ohlc(bars))
        assert chart.column_count == 1
        assert chart.columns[0].type == "X"
        # Top of column = 50 + 9 = 59
        assert chart.columns[0].top == _d("59.00")

    def test_zigzag_creates_multiple_columns(self) -> None:
        """A series of rises and falls each exceeding 3 boxes creates alternating columns."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),    # X starts at 50
            (date(2026, 1, 6), 55.0, 55.0),    # X extends to 55
            (date(2026, 1, 7), 55.0, 51.0),    # X → O, O bottoms at 51
            (date(2026, 1, 8), 58.0, 51.0),    # O → X (top of O was 54, rise 4 boxes), X tops 58
            (date(2026, 1, 9), 58.0, 53.0),    # X → O (top 58, drop to 53, 5 boxes)
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        types = [c.type for c in chart.columns]
        assert types == ["X", "O", "X", "O"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_ohlc_raises(self) -> None:
        df = pd.DataFrame({"high": [], "low": []})
        with pytest.raises(ValueError, match="empty"):
            construct_chart("TEST", df)

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"close": [50.0]}, index=[date(2026, 1, 5)])
        with pytest.raises(ValueError, match="missing required"):
            construct_chart("TEST", df)

    def test_chart_metadata(self) -> None:
        bars = [(date(2026, 1, 5), 50.0, 50.0)]
        chart = construct_chart("MYTICKER", _ohlc(bars))
        assert chart.symbol == "MYTICKER"
        assert chart.box_scaling_label == "traditional"
        assert chart.reversal_boxes == 3

    def test_custom_reversal_boxes(self) -> None:
        """Reversal threshold respects the configured reversal_boxes."""
        # With 5-box reversal, a 3-box drop should NOT reverse
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),
            (date(2026, 1, 6), 55.0, 51.0),  # 4-box drop, would reverse at 3-box rule
        ]
        chart = construct_chart("TEST", _ohlc(bars), reversal_boxes=5)
        assert chart.column_count == 1

    def test_percentage_scaling_produces_chart(self) -> None:
        """Percentage scaling integrates cleanly with the construction algorithm."""
        # Use a high-priced security where percentage scaling makes sense
        bars = [
            (date(2026, 1, 5), 100.0, 100.0),
            (date(2026, 1, 6), 107.0, 100.0),  # ~7% rise, should extend
        ]
        scaling = PercentageScaling(Decimal("0.065"))
        chart = construct_chart("TEST", _ohlc(bars), scaling=scaling)
        assert chart.columns[0].type == "X"
        assert chart.box_scaling_label.startswith("percentage:")


# ---------------------------------------------------------------------------
# Chart properties
# ---------------------------------------------------------------------------


class TestChartProperties:
    def test_current_column_returns_last(self) -> None:
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),
            (date(2026, 1, 6), 55.0, 51.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        assert chart.current_column is not None
        assert chart.current_column.type == "O"

    def test_height_boxes_calculation(self) -> None:
        """An X column from 50 to 55 with $1 boxes has 6 boxes (50,51,52,53,54,55)."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 55.0, 50.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        assert chart.columns[0].height_boxes == 6
