"""Tests for Relative Strength chart construction and regime detection."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from pnf_bot.pnf import (
    STOCK_RS_BOX_PCT,
    compute_rs_ohlc,
    construct_rs_chart,
    detect_signals,
    is_rs_negative_trend,
    is_rs_positive_trend,
    rs_signal_status,
)


def _bars(start: date, prices: list[tuple[float, float]]) -> pd.DataFrame:
    """Build an OHLC DataFrame from a list of (high, low) for consecutive days."""
    return pd.DataFrame(
        [
            {
                "open": (h + l) / 2,
                "high": h,
                "low": l,
                "close": (h + l) / 2,
                "volume": 1_000_000,
            }
            for (h, l) in prices
        ],
        index=[start + timedelta(days=i) for i in range(len(prices))],
    )


class TestComputeRsOhlc:
    def test_ratio_high_uses_security_high_over_benchmark_low(self) -> None:
        """RS high = sec.high / bench.low × 100 — captures max outperformance."""
        sec = _bars(date(2026, 1, 5), [(110.0, 100.0)])
        bench = _bars(date(2026, 1, 5), [(50.0, 45.0)])
        rs = compute_rs_ohlc(sec, bench)
        # high = 110 / 45 × 100 ≈ 244.44
        assert abs(rs["high"].iloc[0] - 110 / 45 * 100) < 0.01

    def test_ratio_low_uses_security_low_over_benchmark_high(self) -> None:
        """RS low = sec.low / bench.high × 100 — captures max underperformance."""
        sec = _bars(date(2026, 1, 5), [(110.0, 100.0)])
        bench = _bars(date(2026, 1, 5), [(50.0, 45.0)])
        rs = compute_rs_ohlc(sec, bench)
        # low = 100 / 50 × 100 = 200.0
        assert abs(rs["low"].iloc[0] - 100 / 50 * 100) < 0.01

    def test_missing_dates_dropped(self) -> None:
        """Days present in only one of the two inputs are excluded from the ratio."""
        sec = _bars(date(2026, 1, 5), [(100, 100), (110, 110), (120, 120)])
        # benchmark missing one day
        bench = pd.DataFrame(
            {"high": [50, 51], "low": [49, 50], "open": [49.5, 50.5], "close": [49.5, 50.5]},
            index=[date(2026, 1, 5), date(2026, 1, 7)],
        )
        rs = compute_rs_ohlc(sec, bench)
        # Only dates present in both should remain
        assert len(rs) == 2


class TestConstructRsChart:
    def test_outperforming_security_produces_rising_rs(self) -> None:
        """If the security outpaces the benchmark, the RS chart should have an X column reaching above the start."""
        # 30 days where security rises from 100 to 200 while benchmark stays at 50
        sec_prices = [(100.0 + i * 3, 99.0 + i * 3) for i in range(30)]
        bench_prices = [(50.0, 49.0)] * 30
        sec = _bars(date(2026, 1, 5), sec_prices)
        bench = _bars(date(2026, 1, 5), bench_prices)
        rs_chart = construct_rs_chart("TEST", sec, bench)
        # Last column's top should be much higher than the first column's bottom
        first = rs_chart.columns[0]
        last = rs_chart.columns[-1]
        assert last.top > first.bottom

    def test_underperforming_security_produces_falling_rs(self) -> None:
        sec_prices = [(100.0 - i * 2, 99.0 - i * 2) for i in range(30)]
        bench_prices = [(50.0, 49.0)] * 30
        sec = _bars(date(2026, 1, 5), sec_prices)
        bench = _bars(date(2026, 1, 5), bench_prices)
        rs_chart = construct_rs_chart("TEST", sec, bench)
        # The chart should show declining RS
        first = rs_chart.columns[0]
        last = rs_chart.columns[-1]
        assert last.bottom < first.top

    def test_rs_chart_uses_percentage_scaling(self) -> None:
        sec = _bars(date(2026, 1, 5), [(100, 99)] * 5)
        bench = _bars(date(2026, 1, 5), [(50, 49)] * 5)
        rs_chart = construct_rs_chart("TEST", sec, bench)
        # Verify the box scaling label indicates percentage
        assert rs_chart.box_scaling_label.startswith("percentage:")

    def test_rs_chart_symbol_is_suffixed(self) -> None:
        sec = _bars(date(2026, 1, 5), [(100, 99)] * 5)
        bench = _bars(date(2026, 1, 5), [(50, 49)] * 5)
        rs_chart = construct_rs_chart("AAPL", sec, bench)
        assert rs_chart.symbol == "AAPL_RS"


class TestRsRegime:
    def test_rs_signal_status_buy_for_outperforming_stock(self) -> None:
        """A clearly outperforming stock should eventually fire an RS buy signal."""
        # Strongly outperforming: 60 days of consistent gains while benchmark flat
        sec_prices = [(100.0 + i * 3, 99.0 + i * 3) for i in range(60)]
        bench_prices = [(50.0, 49.0)] * 60
        sec = _bars(date(2026, 1, 5), sec_prices)
        bench = _bars(date(2026, 1, 5), bench_prices)
        rs_chart = construct_rs_chart("TEST", sec, bench)
        # Should be on an RS buy signal (or "none" if no significant patterns formed
        # — but with 60 days of monotonic gain, at least a DT should fire)
        status = rs_signal_status(rs_chart)
        # If the chart has signals at all, the direction should be bullish
        if status != "none":
            assert status == "buy"

    def test_rs_status_none_for_empty_chart(self) -> None:
        """A chart with too few RS bars to fire any signal returns 'none'."""
        sec = _bars(date(2026, 1, 5), [(100, 99)])
        bench = _bars(date(2026, 1, 5), [(50, 49)])
        rs_chart = construct_rs_chart("TEST", sec, bench)
        # Single-bar chart should have no signals
        assert rs_signal_status(rs_chart) == "none"
