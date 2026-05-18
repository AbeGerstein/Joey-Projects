"""Tests for compound P&F signal detectors (Phase 2C).

Compound signals require multi-column patterns:
- Bullish/Bearish Catapult: TT/TB → pullback → DT/DB
- Bullish/Bearish Triangle: coiling pattern → breakout
- Long Tail Down/Up: capitulation column (≥17 boxes) followed by reversal
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from pnf_bot.pnf import construct_chart, detect_signals


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
# Bullish Catapult
# ---------------------------------------------------------------------------


class TestBullishCatapult:
    def test_simple_bullish_catapult(self) -> None:
        """TT pattern then pullback then DT breakout = catapult.

        Column sequence (alternating X/O starting with X):
            i=0: X tops at 55       (X-6 in the catapult window)
            i=1: O bottoms at 51
            i=2: X tops at 55       (X-4 — same as X-6 → triple-top setup)
            i=3: O bottoms at 51
            i=4: X tops at 57       (X-2 — fires TT)
            i=5: O bottoms at 53    (pullback after TT)
            i=6: X tops at 58       (current — fires DT relative to X-2 → catapult)
        """
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 55.0, 51.0),
            (date(2026, 1, 8), 55.0, 51.0),
            (date(2026, 1, 9), 57.0, 51.0),  # TT fires here
            (date(2026, 1, 10), 57.0, 53.0),  # pullback
            (date(2026, 1, 11), 58.0, 53.0),  # catapult confirmation
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        catapult = [s for s in signals if s.type == "bullish_catapult"]
        assert len(catapult) == 1
        assert catapult[0].direction == "bullish"
        assert catapult[0].price_level == _d("58.00")  # X-2 top (57) + 1 box

    def test_no_catapult_without_prior_tt(self) -> None:
        """A simple DT (no prior TT) should not produce a catapult."""
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 56.0, 51.0),  # DT but no prior TT
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        assert not any(s.type == "bullish_catapult" for s in signals)


# ---------------------------------------------------------------------------
# Bearish Catapult
# ---------------------------------------------------------------------------


class TestBearishCatapult:
    def test_simple_bearish_catapult(self) -> None:
        """TB pattern → bounce → DB breakdown = bearish catapult.

        Mirror of bullish catapult: declining O bottoms with two at same level,
        then a deeper O that fires TB, a bounce X, and a deeper O that fires DB.
        """
        bars = [
            (date(2026, 1, 5), 55.0, 55.0),     # X1 at 55
            (date(2026, 1, 6), 55.0, 50.0),     # O1 bottoms at 50
            (date(2026, 1, 7), 54.0, 50.0),     # X2 to 54
            (date(2026, 1, 8), 54.0, 50.0),     # O2 same bottom 50
            (date(2026, 1, 9), 54.0, 50.0),     # X3 to 54
            (date(2026, 1, 10), 54.0, 49.0),    # O3 fires TB (bottoms below TT-style equal bottoms)
            (date(2026, 1, 11), 54.0, 49.0),    # X4 bounce to 54
            (date(2026, 1, 12), 54.0, 48.0),    # O4 fires DB → bearish catapult
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        catapult = [s for s in signals if s.type == "bearish_catapult"]
        assert len(catapult) == 1
        assert catapult[0].price_level == _d("48.00")


# ---------------------------------------------------------------------------
# Bullish Triangle
# ---------------------------------------------------------------------------


class TestBullishTriangle:
    def test_simple_bullish_triangle(self) -> None:
        """Three X columns with decreasing tops + three O columns with rising bottoms,
        then a breakout DT = bullish triangle.

        Sequence (chronological, with $1 boxes at $20-$100 tier):
            X1 top 99     O1 bottom 70
            X2 top 95     O2 bottom 80
            X3 top 92     O3 bottom 85
            X4 top 93     (DT relative to X3 = 93 > 92 → triangle breakout)

        Tops: 99 > 95 > 92 (falling). Bottoms: 70 < 80 < 85 (rising). Coil ✓.
        """
        bars = [
            (date(2026, 1, 5), 99.0, 99.0),     # X1 anchor at 99
            (date(2026, 1, 6), 99.0, 70.0),     # O1: 70
            (date(2026, 1, 7), 95.0, 70.0),     # X2: top 95
            (date(2026, 1, 8), 95.0, 80.0),     # O2: 80
            (date(2026, 1, 9), 92.0, 80.0),     # X3: top 92
            (date(2026, 1, 10), 92.0, 85.0),    # O3: 85
            (date(2026, 1, 11), 93.0, 85.0),    # X4: breakout to 93
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        triangle = [s for s in signals if s.type == "bullish_triangle"]
        assert len(triangle) >= 1
        assert triangle[0].direction == "bullish"


# ---------------------------------------------------------------------------
# Bearish Triangle
# ---------------------------------------------------------------------------


class TestBearishTriangle:
    def test_simple_bearish_triangle(self) -> None:
        """Same coil pattern as bullish triangle but breaks DOWN with a DB.

        Sequence:
            X1 top 99    O1 bottom 70
            X2 top 95    O2 bottom 80
            X3 top 92    O3 bottom 85
            X4 top 90    (does NOT fire DT — top < X3.top + box)
            O4 bottom 84 (DB vs O3 bottom 85 → bearish triangle breakdown)
        """
        bars = [
            (date(2026, 1, 5), 99.0, 99.0),     # X1
            (date(2026, 1, 6), 99.0, 70.0),     # O1: 70
            (date(2026, 1, 7), 95.0, 70.0),     # X2: top 95
            (date(2026, 1, 8), 95.0, 80.0),     # O2: 80
            (date(2026, 1, 9), 92.0, 80.0),     # X3: top 92
            (date(2026, 1, 10), 92.0, 85.0),    # O3: 85
            (date(2026, 1, 11), 90.0, 85.0),    # X4: top 90 (no DT)
            (date(2026, 1, 12), 90.0, 84.0),    # O4: bottom 84 → DB + bearish triangle
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart)
        triangle = [s for s in signals if s.type == "bearish_triangle"]
        assert len(triangle) >= 1
        assert triangle[0].direction == "bearish"


# ---------------------------------------------------------------------------
# Long Tail
# ---------------------------------------------------------------------------


class TestLongTailDown:
    def test_long_tail_down_fires_after_17_box_o_column(self) -> None:
        """An O column of >=17 boxes followed by an X column produces long_tail_down.

        Need to construct: X column anchored high, then a deep O column with 17+
        boxes, then an X reversal.
        """
        # Start at 80, drop dramatically to trigger long O column
        bars = [
            (date(2026, 1, 5), 80.0, 80.0),     # X anchor at 80
        ]
        # Day 2: extreme drop creating a 20+ box O column (boxes are $1 at this tier)
        bars.append((date(2026, 1, 6), 80.0, 60.0))  # O column 79 down to 60 = 20 boxes
        # Day 3: X reversal — high rises >=3 boxes from O bottom
        bars.append((date(2026, 1, 7), 70.0, 60.0))  # X rises to 70
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart, long_tail_boxes=17)
        lt = [s for s in signals if s.type == "long_tail_down"]
        assert len(lt) == 1
        assert lt[0].direction == "bullish"  # bullish reversal off the capitulation low

    def test_long_tail_down_not_fired_for_short_o_column(self) -> None:
        bars = [
            (date(2026, 1, 5), 80.0, 80.0),
            (date(2026, 1, 6), 80.0, 75.0),  # only 5 boxes
            (date(2026, 1, 7), 78.0, 75.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart, long_tail_boxes=17)
        assert not any(s.type == "long_tail_down" for s in signals)


class TestLongTailUp:
    def test_long_tail_up_fires_after_17_box_x_column(self) -> None:
        """An X column of >=17 boxes followed by an O column produces long_tail_up."""
        bars = [
            (date(2026, 1, 5), 50.0, 50.0),
            (date(2026, 1, 6), 75.0, 50.0),  # X to 75 (25-box rally at $1 boxes)
            (date(2026, 1, 7), 75.0, 65.0),  # O retraces
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        signals = detect_signals(chart, long_tail_boxes=17)
        lt = [s for s in signals if s.type == "long_tail_up"]
        assert len(lt) == 1
        assert lt[0].direction == "bearish"


class TestCompoundSignalsConfig:
    """Verify the threshold parameters work as intended."""

    def test_long_tail_threshold_configurable(self) -> None:
        bars = [
            (date(2026, 1, 5), 80.0, 80.0),
            (date(2026, 1, 6), 80.0, 73.0),  # 7-box drop
            (date(2026, 1, 7), 76.0, 73.0),
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        # With default 17, no long tail
        assert not any(
            s.type == "long_tail_down" for s in detect_signals(chart)
        )
        # With threshold 5, the 7-box drop qualifies
        signals = detect_signals(chart, long_tail_boxes=5)
        assert any(s.type == "long_tail_down" for s in signals)
