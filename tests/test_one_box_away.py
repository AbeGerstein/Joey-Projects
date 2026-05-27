"""Tests for the one-box-away pattern detector."""

from __future__ import annotations

from datetime import date

import pandas as pd

from pnf_bot.pnf import construct_chart
from pnf_bot.pnf.signals import detect_signals
from pnf_bot.scoring.one_box_away import (
    CHECKLIST_QUALIFYING_PATTERNS,
    fired_today,
    one_box_away,
    one_box_away_from_rs_buy,
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


class TestQualifyingPatterns:
    def test_excludes_double_top(self) -> None:
        """Double_top must be explicitly excluded — that's per the advisor's spec."""
        assert "double_top" not in CHECKLIST_QUALIFYING_PATTERNS

    def test_contains_all_10_patterns(self) -> None:
        expected = {
            "triple_top",
            "quadruple_top",
            "quintuple_top",
            "spread_triple_top",
            "spread_quadruple_top",
            "spread_quintuple_top",
            "shakeout",
            "bullish_triangle",
            "bullish_catapult",
            "bearish_signal_reversal",
        }
        assert expected == CHECKLIST_QUALIFYING_PATTERNS


class TestOneBoxAway:
    def test_one_box_from_triple_top(self) -> None:
        """Two prior X cols at 55; current X col at 55 (TT not yet fired).
        Add one box → top becomes 56 → TT fires.
        """
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),    # X1 at 55
            (date(2026, 1, 6), 55.0, 51.0),    # O
            (date(2026, 1, 7), 55.0, 51.0),    # X2 at 55
            (date(2026, 1, 8), 55.0, 51.0),    # O
            (date(2026, 1, 9), 55.0, 51.0),    # X3 at 55 (one box from TT)
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        result = one_box_away(chart)
        assert "triple_top" in result

    def test_no_match_when_pattern_already_fired(self) -> None:
        """A chart that already fired TT shouldn't show TT as one-box-away."""
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 55.0, 51.0),
            (date(2026, 1, 8), 55.0, 51.0),
            (date(2026, 1, 9), 56.0, 51.0),    # X3 at 56 — TT fires
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        # Check TT already fires
        sigs = detect_signals(chart)
        assert any(s.type == "triple_top" for s in sigs)
        # Now one_box_away should NOT report TT
        result = one_box_away(chart)
        assert "triple_top" not in result

    def test_returns_empty_when_current_is_o(self) -> None:
        """Chart in O column — no patterns one box away (need reversal first)."""
        bars = [
            (date(2026, 1, 5), 60.0, 55.0),    # X up to 60
            (date(2026, 1, 6), 60.0, 50.0),    # O down to 50 (3-box reversal)
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        # Verify chart is in O col
        assert chart.columns[-1].type == "O"
        result = one_box_away(chart)
        assert result == set()

    def test_empty_chart_returns_empty(self) -> None:
        from pnf_bot.pnf.types import PnFChart

        chart = PnFChart(symbol="X", columns=(), box_scaling_label="traditional")
        assert one_box_away(chart) == set()


class TestFiredToday:
    def test_returns_only_signals_on_specific_date(self) -> None:
        """Filter to signals that fired on the most recent trading day."""
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 55.0, 51.0),
            (date(2026, 1, 8), 55.0, 51.0),
            (date(2026, 1, 9), 56.0, 51.0),   # X3 fires TT on 1/9
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        sigs = detect_signals(chart)
        fired_on_target = fired_today(sigs, date(2026, 1, 9))
        assert "triple_top" in fired_on_target
        # And nothing on an earlier date
        fired_earlier = fired_today(sigs, date(2026, 1, 6))
        assert "triple_top" not in fired_earlier

    def test_excludes_double_top_from_today_set(self) -> None:
        """The qualifying set excludes double_top, so DT firing today should
        NOT appear in fired_today's result."""
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 56.0, 51.0),  # DT fires (no triple structure)
        ]
        chart = construct_chart("TEST", _ohlc(bars))
        sigs = detect_signals(chart)
        # Find DT's fired_date
        dt_sig = next(s for s in sigs if s.type == "double_top")
        result = fired_today(sigs, dt_sig.fired_date)
        assert "double_top" not in result


class TestOneBoxAwayFromRsBuy:
    def test_rs_chart_one_box_from_dt(self) -> None:
        """RS chart with X col one box below the DT trigger level."""
        bars = [
            (date(2026, 1, 5), 100.0, 95.0),    # base X
            (date(2026, 1, 6), 100.0, 90.0),    # O
            (date(2026, 1, 7), 100.0, 96.0),    # X at 100 (= prior X top; one box from DT)
        ]
        # Construct as a price chart (we just need the structure)
        chart = construct_chart("RS", _ohlc(bars))
        # Current col top should be at or just below the DT trigger
        # The detector returns True when adding one box would fire a buy signal
        result = one_box_away_from_rs_buy(chart)
        # Either currently DT fires or not — what we want: extending by one box
        # changes the bullish-signal set.
        if chart.columns[-1].type == "X":
            # If current top equals or exceeds prior X top, DT might fire already.
            # In that case the answer is False (already firing, not "one box away").
            sigs = detect_signals(chart)
            already_dt = any(
                s.type == "double_top" and s.column_index == len(chart.columns) - 1
                for s in sigs
            )
            if already_dt:
                assert result is False
            else:
                assert result is True
        else:
            # Current is O — function returns False
            assert result is False

    def test_returns_false_for_none_chart(self) -> None:
        assert one_box_away_from_rs_buy(None) is False
