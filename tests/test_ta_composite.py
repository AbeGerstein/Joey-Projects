"""Tests for the internal TA-equivalent composite score."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

from pnf_bot.pnf import construct_chart
from pnf_bot.scoring.ta_composite import compute_ta_equivalent


def _bars(start: date, hl: list[tuple[float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"open": (h + l) / 2, "high": h, "low": l, "close": (h + l) / 2, "volume": 1_000_000}
            for (h, l) in hl
        ],
        index=[start + timedelta(days=i) for i in range(len(hl))],
    )


class TestTaComposite:
    def test_chart_on_buy_signal_scores_at_least_one(self) -> None:
        """A clean DT chart should score at least 1 (the price-buy signal).

        The above-support condition depends on the chart's specific
        structure — short synthetic charts where the 45° support line
        projects faster than the recovery may not be above support.
        Real-world long-history charts typically are.
        """
        bars = [
            (50.0, 50.0),
            (50.0, 46.0),
            (51.0, 46.0),
            (51.0, 47.0),
            (52.0, 47.0),  # DT
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        ta = compute_ta_equivalent(chart)
        assert ta.score >= 1
        assert ta.on_price_buy_signal is True

    def test_chart_with_strong_recovery_above_support(self) -> None:
        """A chart with a clean low and uninterrupted recovery should be above support."""
        bars = [
            (50.0, 50.0),    # X1
            (50.0, 45.0),    # O1 to 45 (the only O column)
            (51.0, 45.0),    # X2 to 51
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        ta = compute_ta_equivalent(chart)
        # With only ONE O column anchoring support, no subsequent O can have
        # broken the line, so above_bullish_support is True.
        assert ta.above_bullish_support is True

    def test_no_rs_chart_no_rs_credit(self) -> None:
        """Without an RS chart, RS conditions score 0."""
        bars = [
            (50.0, 50.0),
            (50.0, 46.0),
            (51.0, 46.0),
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        ta = compute_ta_equivalent(chart, rs_chart=None)
        assert ta.on_rs_buy_signal is False
        assert ta.rs_positive_trend is False

    def test_favorable_sector_bpi_adds_credit(self) -> None:
        bars = [(50.0, 50.0)]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        ta_neutral = compute_ta_equivalent(chart)
        ta_favorable = compute_ta_equivalent(chart, sector_bpi_state="bull_confirmed")
        assert ta_favorable.favorable_sector_bpi is True
        assert ta_favorable.score == ta_neutral.score + 1

    def test_unfavorable_sector_bpi_no_credit(self) -> None:
        bars = [(50.0, 50.0)]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        ta = compute_ta_equivalent(chart, sector_bpi_state="bear_confirmed")
        assert ta.favorable_sector_bpi is False

    def test_score_bounded_0_to_5(self) -> None:
        bars = [
            (50.0, 50.0),
            (50.0, 46.0),
            (51.0, 46.0),
            (51.0, 47.0),
            (52.0, 47.0),
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        ta = compute_ta_equivalent(chart)
        assert 0 <= ta.score <= 5
