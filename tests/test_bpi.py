"""Tests for BPI computation, classification, and chart construction."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

from pnf_bot.pnf import (
    classify_bpi_state,
    compute_bpi,
    compute_bpi_with_breakdown,
    construct_bpi_chart,
    construct_chart,
    current_signal_posture,
)


def _bars(start: date, hl: list[tuple[float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"open": (h + l) / 2, "high": h, "low": l, "close": (h + l) / 2, "volume": 1_000_000}
            for (h, l) in hl
        ],
        index=[start + timedelta(days=i) for i in range(len(hl))],
    )


class TestCurrentSignalPosture:
    def test_buy_after_double_top(self) -> None:
        bars = [
            (50.0, 50.0),
            (50.0, 46.0),     # O reverses
            (51.0, 46.0),     # X up
            (51.0, 47.0),     # O
            (52.0, 47.0),     # X exceeds prior X (51) → DT
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        assert current_signal_posture(chart) == "buy"

    def test_sell_after_double_bottom(self) -> None:
        bars = [
            (55.0, 55.0),
            (55.0, 50.0),     # O to 50
            (54.0, 50.0),     # X
            (54.0, 49.0),     # O below prior O → DB
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        assert current_signal_posture(chart) == "sell"

    def test_unknown_when_no_signal(self) -> None:
        bars = [(50.0, 50.0)]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        assert current_signal_posture(chart) == "unknown"


class TestComputeBpi:
    def _make_buy_chart(self) -> construct_chart:
        bars = [
            (50.0, 50.0),
            (50.0, 46.0),
            (51.0, 46.0),
            (51.0, 47.0),
            (52.0, 47.0),
        ]
        return construct_chart("T", _bars(date(2026, 1, 5), bars))

    def _make_sell_chart(self) -> construct_chart:
        bars = [
            (55.0, 55.0),
            (55.0, 50.0),
            (54.0, 50.0),
            (54.0, 49.0),
        ]
        return construct_chart("T", _bars(date(2026, 1, 5), bars))

    def test_bpi_all_buy(self) -> None:
        """All stocks on buy → 100%."""
        charts = {f"S{i}": self._make_buy_chart() for i in range(5)}
        assert compute_bpi(charts) == Decimal("100.00")

    def test_bpi_all_sell(self) -> None:
        charts = {f"S{i}": self._make_sell_chart() for i in range(5)}
        assert compute_bpi(charts) == Decimal("0.00")

    def test_bpi_mixed(self) -> None:
        """3 buy + 2 sell → 60%."""
        charts = {}
        for i in range(3):
            charts[f"B{i}"] = self._make_buy_chart()
        for i in range(2):
            charts[f"S{i}"] = self._make_sell_chart()
        assert compute_bpi(charts) == Decimal("60.00")

    def test_bpi_skips_unknown_postures(self) -> None:
        """Stocks with no signal yet are excluded from numerator and denominator."""
        # Two buys + one unknown → BPI 100%, total = 2
        unknown_chart = construct_chart("U", _bars(date(2026, 1, 5), [(50.0, 50.0)]))
        charts = {
            "B1": self._make_buy_chart(),
            "B2": self._make_buy_chart(),
            "U": unknown_chart,
        }
        breakdown = compute_bpi_with_breakdown(charts)
        assert breakdown.bpi_value == Decimal("100.00")
        assert breakdown.total_stocks == 2  # the unknown was excluded
        assert breakdown.stocks_on_buy_signal == 2

    def test_bpi_zero_when_no_determinable(self) -> None:
        unknown_chart = construct_chart("U", _bars(date(2026, 1, 5), [(50.0, 50.0)]))
        charts = {"U1": unknown_chart, "U2": unknown_chart}
        assert compute_bpi(charts) == Decimal("0")


class TestBpiChart:
    def test_construct_bpi_chart_uses_2pp_boxes(self) -> None:
        series = pd.Series(
            [40.0, 50.0, 60.0, 70.0, 80.0],
            index=[date(2026, 1, 5) + timedelta(days=i) for i in range(5)],
        )
        chart = construct_bpi_chart(series)
        assert chart.box_scaling_label == "bpi:2pp"
        # First column should be an X column extending up
        assert chart.columns[0].type == "X"


class TestBpiClassification:
    def _bpi_chart_for(self, values: list[float]) -> construct_bpi_chart:
        idx = [date(2026, 1, 5) + timedelta(days=i) for i in range(len(values))]
        return construct_bpi_chart(pd.Series(values, index=idx))

    def test_bull_confirmed_when_rising(self) -> None:
        """Rising BPI from mid-range → Bull Confirmed."""
        chart = self._bpi_chart_for([40, 42, 44, 46, 48, 50])
        state = classify_bpi_state(chart)
        assert state in ("bull_confirmed", "bull_alert", "bull_correction")

    def test_unknown_for_empty_chart(self) -> None:
        # Empty series can't construct a chart, so build a minimal one
        chart = construct_bpi_chart(pd.Series([50.0], index=[date(2026, 1, 5)]))
        # Single-bar BPI chart still has one column
        assert classify_bpi_state(chart) in (
            "bull_confirmed", "bear_confirmed", "unknown",
            "bull_correction", "bear_correction", "bull_alert", "bear_alert",
        )


class TestPostureRecord:
    def test_evaluate_stock_posture_no_rs(self) -> None:
        from pnf_bot.pnf import evaluate_stock_posture

        bars = [
            (50.0, 50.0),
            (50.0, 46.0),
            (51.0, 46.0),
            (51.0, 47.0),
            (52.0, 47.0),
        ]
        chart = construct_chart("AAPL", _bars(date(2026, 1, 5), bars))
        posture = evaluate_stock_posture("AAPL", chart, as_of_date=date(2026, 1, 10))
        assert posture.symbol == "AAPL"
        assert posture.price_signal_posture == "buy"
        assert posture.rs_signal_status == "none"  # No RS chart provided

    def test_evaluate_stock_posture_with_sector(self) -> None:
        from pnf_bot.pnf import evaluate_stock_posture

        bars = [
            (50.0, 50.0),
            (50.0, 46.0),
            (51.0, 46.0),
        ]
        chart = construct_chart("AAPL", _bars(date(2026, 1, 5), bars))
        posture = evaluate_stock_posture(
            "AAPL", chart, sector="Information Technology",
            sector_bpi=Decimal("65"), sector_bpi_state="bull_confirmed",
        )
        assert posture.sector == "Information Technology"
        assert posture.sector_bpi == Decimal("65")
        assert posture.sector_bpi_state == "bull_confirmed"
