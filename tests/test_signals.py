"""Tests for foundational P&F signal detection.

Each test constructs a synthetic OHLC sequence designed to produce exactly
one signal of a specific type, then verifies the detector identifies it
with the correct type, direction, column index, fire date, and price level.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from pnf_bot.pnf import (
    construct_chart,
    detect_signals,
    latest_signal,
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


# ---------------------------------------------------------------------------
# Double Top / Double Bottom
# ---------------------------------------------------------------------------


class TestDoubleTop:
    def test_simple_double_top(self) -> None:
        """Three-column sequence: X to 55, O down to 51, X exceeds 55 → DT.

        Box size at this price tier ($20-$100) is $1, so DT signal fires
        when the third column reaches 56.
        """
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),     # X column tops at 55
            (date(2026, 1, 6), 55.0, 51.0),     # reverse to O, bottom at 51
            (date(2026, 1, 7), 56.0, 51.0),     # X column exceeds 55 → DT at 56
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        assert any(s.type == "double_top" for s in signals)
        dt = next(s for s in signals if s.type == "double_top")
        assert dt.direction == "bullish"
        assert dt.column_index == 2  # the third column (0-indexed)
        assert dt.price_level == _d("56.00")
        assert dt.fired_date == date(2026, 1, 7)

    def test_no_double_top_if_third_column_doesnt_exceed(self) -> None:
        """If the third X column doesn't make a new high above the first, no DT."""
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 54.0, 51.0),  # only reaches 54, not above 55
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        # No DT because the third column only reaches 54 (and didn't even create a new X column)
        assert not any(s.type == "double_top" for s in signals)

    def test_dt_fire_date_is_exact_breakout_day(self) -> None:
        """DT signal date should be the day price first reached the breakout level.

        Even if the column extends further later, the signal date stays the day
        of the original breakout.
        """
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),     # X to 55
            (date(2026, 1, 6), 55.0, 51.0),     # O to 51
            (date(2026, 1, 7), 56.0, 51.0),     # X to 56 — DT fires here
            (date(2026, 1, 8), 58.0, 51.0),     # X extends to 58
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        dt = next(s for s in detect_signals(chart) if s.type == "double_top")
        assert dt.fired_date == date(2026, 1, 7)  # NOT 1/8 even though column extended further


class TestDoubleBottom:
    def test_simple_double_bottom(self) -> None:
        """X, O at bottom 50, X up, O exceeds 50 to the downside → DB at 49."""
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),     # X at 55
            (date(2026, 1, 6), 55.0, 50.0),     # O down to 50
            (date(2026, 1, 7), 54.0, 50.0),     # X back up to 54
            (date(2026, 1, 8), 54.0, 49.0),     # O down through 50 to 49 → DB at 49
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        assert any(s.type == "double_bottom" for s in signals)
        db = next(s for s in signals if s.type == "double_bottom")
        assert db.direction == "bearish"
        assert db.price_level == _d("49.00")
        assert db.fired_date == date(2026, 1, 8)


# ---------------------------------------------------------------------------
# Triple Top / Triple Bottom
# ---------------------------------------------------------------------------


class TestTripleTop:
    def test_triple_top_exact_match(self) -> None:
        """Two prior X columns both topping at 55, then a third exceeding → TT at 56."""
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),     # X1 tops at 55
            (date(2026, 1, 6), 55.0, 51.0),     # O1 to 51
            (date(2026, 1, 7), 55.0, 51.0),     # X2 tops at 55 (same as X1)
            (date(2026, 1, 8), 55.0, 51.0),     # O2 to 51
            (date(2026, 1, 9), 56.0, 51.0),     # X3 exceeds → TT at 56
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        tt_signals = [s for s in signals if s.type == "triple_top"]
        assert len(tt_signals) >= 1
        tt = tt_signals[0]
        assert tt.direction == "bullish"
        assert tt.price_level == _d("56.00")
        assert tt.fired_date == date(2026, 1, 9)

    def test_triple_top_also_produces_double_top(self) -> None:
        """A TT setup is also a DT (it crosses the immediately preceding X top)."""
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 55.0, 51.0),
            (date(2026, 1, 8), 55.0, 51.0),
            (date(2026, 1, 9), 56.0, 51.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        # Both DT and TT should fire on the same column
        types = {s.type for s in signals}
        assert "double_top" in types
        assert "triple_top" in types


class TestTripleBottom:
    def test_triple_bottom_exact_match(self) -> None:
        """Two prior O columns both bottoming at 50, third O exceeds → TB at 49."""
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),     # X1 at 55
            (date(2026, 1, 6), 54.0, 50.0),     # O1 to 50
            (date(2026, 1, 7), 54.0, 50.0),     # X2 back up to 54
            (date(2026, 1, 8), 54.0, 50.0),     # O2 to 50 (same as O1)
            (date(2026, 1, 9), 54.0, 50.0),     # X3 to 54
            (date(2026, 1, 10), 54.0, 49.0),    # O3 exceeds → TB at 49
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        tb_signals = [s for s in signals if s.type == "triple_bottom"]
        assert len(tb_signals) >= 1
        tb = tb_signals[0]
        assert tb.direction == "bearish"
        assert tb.price_level == _d("49.00")


# ---------------------------------------------------------------------------
# Spread Triple Top / Bottom
# ---------------------------------------------------------------------------


class TestSpreadTripleTop:
    def test_spread_triple_top_with_two_box_separation(self) -> None:
        """Two prior X columns at 55 and 56 (1 box apart, within tolerance);
        third X exceeds both → Spread TT at 57.
        """
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 56.0, 51.0),  # X2 tops at 56 (1 box above X1)
            (date(2026, 1, 8), 56.0, 51.0),
            (date(2026, 1, 9), 57.0, 51.0),  # X3 exceeds both → spread TT at 57
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        spread = [s for s in signals if s.type == "spread_triple_top"]
        assert len(spread) >= 1
        assert spread[0].price_level == _d("57.00")

    def test_spread_does_not_fire_when_tops_are_identical(self) -> None:
        """When prior tops are identical, that's a regular TT, NOT a spread TT.

        The detector should fire TT but not spread TT.
        """
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 55.0, 51.0),
            (date(2026, 1, 8), 55.0, 51.0),
            (date(2026, 1, 9), 56.0, 51.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        assert not any(s.type == "spread_triple_top" for s in signals)
        # But TT does fire
        assert any(s.type == "triple_top" for s in signals)

    def test_spread_does_not_fire_outside_tolerance(self) -> None:
        """Two prior X columns 4 boxes apart exceed the default 2-box tolerance."""
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),    # X1 tops 55
            (date(2026, 1, 6), 55.0, 51.0),    # O
            (date(2026, 1, 7), 59.0, 51.0),    # X2 tops 59 (4 boxes above X1)
            (date(2026, 1, 8), 59.0, 51.0),    # O
            (date(2026, 1, 9), 60.0, 51.0),    # X3 exceeds X2 → DT but not spread TT
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart, spread_tolerance_boxes=2)
        assert not any(s.type == "spread_triple_top" for s in signals)


class TestSpreadTripleBottom:
    def test_spread_triple_bottom_within_tolerance(self) -> None:
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),
            (date(2026, 1, 6), 55.0, 50.0),    # O1 bottoms at 50
            (date(2026, 1, 7), 54.0, 50.0),    # X
            (date(2026, 1, 8), 54.0, 49.0),    # O2 bottoms at 49 (1 box below O1)
            (date(2026, 1, 9), 53.0, 49.0),    # X
            (date(2026, 1, 10), 53.0, 48.0),   # O3 exceeds both → spread TB at 48
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        spread = [s for s in signals if s.type == "spread_triple_bottom"]
        assert len(spread) >= 1
        assert spread[0].price_level == _d("48.00")


# ---------------------------------------------------------------------------
# Helpers / integration
# ---------------------------------------------------------------------------


class TestLatestSignal:
    def test_latest_returns_most_recent(self) -> None:
        """latest_signal returns the most recently fired signal."""
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 56.0, 51.0),  # DT here
            (date(2026, 1, 8), 56.0, 52.0),
            (date(2026, 1, 9), 56.0, 52.0),  # tries to be O but doesn't reverse
            (date(2026, 1, 10), 56.0, 52.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        latest = latest_signal(chart)
        assert latest is not None
        assert latest.type == "double_top"

    def test_latest_signal_returns_none_for_no_signals(self) -> None:
        """A simple two-column chart (X then partial O) has no signals."""
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        assert latest_signal(chart) is None


class TestSignalProperties:
    def test_is_bullish_and_is_bearish(self) -> None:
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 56.0, 51.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        dt = next(s for s in detect_signals(chart) if s.type == "double_top")
        assert dt.is_bullish is True
        assert dt.is_bearish is False


class TestExtensionHistory:
    """Verify the Column.extension_history field is populated correctly."""

    def test_simple_extension_history(self) -> None:
        """X column extending to a new high records each extension."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 51.0, 50.0),
            (date(2026, 1, 7), 53.0, 51.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        col = chart.columns[0]
        # History should have 3 entries — initial 50, extension to 51, extension to 53
        levels = [level for (_, level) in col.extension_history]
        assert _d("50.00") in levels
        assert _d("51.00") in levels
        assert _d("53.00") in levels

    def test_date_when_extreme_reached(self) -> None:
        """Column.date_when_extreme_reached returns the first date past a threshold."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 53.0, 50.0),  # extended through 52 on this day
            (date(2026, 1, 7), 55.0, 51.0),  # further extension
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        col = chart.columns[0]
        # Looking for the first date when top >= 52
        d = col.date_when_extreme_reached(_d("52.00"))
        assert d == date(2026, 1, 6)
