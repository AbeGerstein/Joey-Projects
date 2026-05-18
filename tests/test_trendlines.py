"""Tests for 45° trendline detection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd

from pnf_bot.pnf import (
    boxes_above_bullish_support,
    construct_chart,
    find_bearish_resistance_line,
    find_bullish_support_line,
    is_above_bullish_support,
    is_below_bearish_resistance,
)


def _ohlc(bars: list[tuple[date, float, float]]) -> pd.DataFrame:
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


class TestBullishSupportLine:
    def test_line_anchored_at_lowest_o(self) -> None:
        """The bullish support line is anchored just above the lowest O column."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),     # X1 anchor
            (date(2026, 1, 6), 50.0, 45.0),     # O1: bottom 45 (lowest)
            (date(2026, 1, 7), 50.0, 45.0),     # X2 to 49
            (date(2026, 1, 8), 49.0, 46.0),     # O2: bottom 46
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        line = find_bullish_support_line(chart)
        assert line is not None
        assert line.type == "bullish_support"
        # Anchor price = lowest O bottom + box_size = 45 + 1 = 46
        assert line.anchor_price == _d("46.00")
        assert line.box_size == _d("1.00")

    def test_line_slopes_up_one_box_per_column(self) -> None:
        """45° line: each column to the right adds one box to the price."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 50.0, 45.0),     # O1 bottom 45
            (date(2026, 1, 7), 50.0, 45.0),     # X2 to 49
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        line = find_bullish_support_line(chart)
        assert line is not None
        # Line at anchor column = anchor_price = 46
        anchor_idx = line.anchor_column_index
        assert line.price_at_column(anchor_idx) == _d("46.00")
        # Three columns later: 46 + 3 = 49
        assert line.price_at_column(anchor_idx + 3) == _d("49.00")

    def test_no_line_without_o_columns(self) -> None:
        """A chart with only X columns has no bullish support line."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 51.0, 50.0),
            (date(2026, 1, 7), 52.0, 51.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        line = find_bullish_support_line(chart)
        assert line is None


class TestBearishResistanceLine:
    def test_line_anchored_at_highest_x(self) -> None:
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 55.0, 50.0),     # X1 top 55 (will be the highest)
            (date(2026, 1, 7), 55.0, 51.0),     # O1 to 51
            (date(2026, 1, 8), 54.0, 51.0),     # X2 to 54
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        line = find_bearish_resistance_line(chart)
        assert line is not None
        assert line.type == "bearish_resistance"
        # Anchor at highest X.top - box_size = 55 - 1 = 54
        assert line.anchor_price == _d("54.00")

    def test_line_slopes_down(self) -> None:
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),     # X1 anchor at 55
            (date(2026, 1, 6), 55.0, 51.0),     # O1 to 51
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        line = find_bearish_resistance_line(chart)
        assert line is not None
        anchor_idx = line.anchor_column_index
        assert line.price_at_column(anchor_idx) == _d("54.00")
        assert line.price_at_column(anchor_idx + 3) == _d("51.00")


class TestTrendPostureHelpers:
    def test_is_above_bullish_support_when_price_holds(self) -> None:
        """Stock that pulled back to support and held should be above support."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),    # X1
            (date(2026, 1, 6), 50.0, 45.0),    # O1 bottom 45 → support at 46
            (date(2026, 1, 7), 50.0, 45.0),    # X2 to 49 (above 46)
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        assert is_above_bullish_support(chart) is True

    def test_boxes_above_support_counts_distance(self) -> None:
        """An extended stock should be many boxes above the support line."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 50.0, 45.0),    # O1 lowest at 45 → support at 46
            (date(2026, 1, 7), 50.0, 45.0),    # X2
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        # Current X column should be a few boxes above support
        boxes_above = boxes_above_bullish_support(chart)
        assert boxes_above >= 0

    def test_is_below_bearish_resistance_after_breakdown(self) -> None:
        """A stock pinned by resistance should be below it."""
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),     # X1 top 55 → resistance at 54
            (date(2026, 1, 6), 55.0, 50.0),     # O1 to 50 (below resistance projection)
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        # Current is the O column at 50 — should be below the bearish resistance line
        # (which projects DOWN from 54 by 1 box per column).
        # At column 1 (anchor column for the line), line_price = 54.
        # Current.top = 50, which is < 54.
        assert is_below_bearish_resistance(chart) is True


class TestTrendlineEdgeCases:
    def test_lookback_window_limits_search(self) -> None:
        """A lookback_columns parameter limits the support/resistance search."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 50.0, 40.0),    # O1: very low (40)
            (date(2026, 1, 7), 50.0, 40.0),    # X2
            (date(2026, 1, 8), 50.0, 45.0),    # O2: less low (45)
            (date(2026, 1, 9), 50.0, 45.0),    # X3
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        # Full lookback: support anchored at O1 bottom 40 + 1 = 41
        full_line = find_bullish_support_line(chart)
        assert full_line is not None
        assert full_line.anchor_price == _d("41.00")
        # Limited lookback to last 3 columns: should pick O2 (bottom 45)
        limited_line = find_bullish_support_line(chart, lookback_columns=3)
        assert limited_line is not None
        assert limited_line.anchor_price == _d("46.00")
