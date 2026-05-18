"""Tests for per-stock detail compilation and HTML report rendering."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from pnf_bot.pnf import construct_chart
from pnf_bot.report.detail import StockDetailRecord, compile_stock_detail
from pnf_bot.report.render import render_html_report
from pnf_bot.scoring.composite import DailyReport, ScoredCandidate, build_daily_report
from pnf_bot.scoring.composite import score_stock_pre_momentum


def _bars(start: date, hl: list[tuple[float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"open": (h + l) / 2, "high": h, "low": l, "close": (h + l) / 2, "volume": 1_000_000}
            for (h, l) in hl
        ],
        index=[start + timedelta(days=i) for i in range(len(hl))],
    )


def _build_candidate(symbol: str) -> tuple[ScoredCandidate, "construct_chart"]:
    bars = [
        (50.0, 50.0),
        (50.0, 45.0),
        (51.0, 45.0),
    ]
    chart = construct_chart(symbol, _bars(date(2026, 1, 5), bars))
    # Synthesize a candidate (rather than relying on score_stock_pre_momentum to return one)
    candidate = ScoredCandidate(
        symbol=symbol,
        section="pre_momentum",
        base_score=0.5,
        freshness_multiplier=2.0,
        final_score=1.0,
        matched_patterns=(),
        most_recent_pattern_date=date(2026, 1, 10),
        ta_equivalent_score=3,
        fired_last_night=True,
    )
    return candidate, chart


class TestCompileStockDetail:
    def test_compiles_record_with_all_fields(self) -> None:
        candidate, chart = _build_candidate("AAPL")
        detail = compile_stock_detail(
            candidate, chart,
            company_name="Apple Inc.",
            sector="Information Technology",
        )
        assert detail.symbol == "AAPL"
        assert detail.company_name == "Apple Inc."
        assert detail.sector == "Information Technology"
        assert detail.pnf_chart_b64  # non-empty base64 string
        assert detail.rs_chart_b64 is None  # no RS chart provided
        assert detail.final_score == 1.0

    def test_compiles_with_rs_chart(self) -> None:
        candidate, chart = _build_candidate("AAPL")
        # Use the same chart as a stand-in for RS
        detail = compile_stock_detail(candidate, chart, rs_chart=chart)
        assert detail.rs_chart_b64 is not None

    def test_suggested_stop_below_current(self) -> None:
        candidate, chart = _build_candidate("AAPL")
        detail = compile_stock_detail(candidate, chart)
        if detail.suggested_stop is not None and detail.current_price is not None:
            assert detail.suggested_stop <= detail.current_price


class TestRenderHtmlReport:
    def test_renders_full_html(self) -> None:
        candidate, chart = _build_candidate("AAPL")
        detail = compile_stock_detail(candidate, chart, company_name="Apple Inc.")
        report = build_daily_report([candidate], as_of_date=date(2026, 1, 15))
        html = render_html_report(report, [detail], [])
        # Check the major structural elements
        assert "<!DOCTYPE html>" in html
        assert "Daily PnF stock report" in html
        assert "AAPL" in html
        assert "Apple Inc." in html
        assert "DISCLAIMER" in html
        # The new-patterns callout should be present (fired_last_night=True)
        assert "New Patterns from Last Night" in html

    def test_empty_report_still_renders(self) -> None:
        empty_report = DailyReport(
            as_of_date=date(2026, 1, 15),
            new_patterns_last_night=(),
            section_a_top_n=(),
            section_b_top_n=(),
        )
        html = render_html_report(empty_report, [], [])
        assert "Daily PnF stock report" in html
        assert "DISCLAIMER" in html

    def test_in_momentum_only_report(self) -> None:
        candidate, chart = _build_candidate("MSFT")
        # Switch to in_momentum section
        in_candidate = ScoredCandidate(
            symbol="MSFT", section="in_momentum",
            base_score=0.6, freshness_multiplier=1.0, final_score=0.6,
            matched_patterns=(),
            most_recent_pattern_date=date(2026, 1, 12),
            ta_equivalent_score=4, fired_last_night=False,
        )
        detail = compile_stock_detail(in_candidate, chart)
        report = build_daily_report([in_candidate], as_of_date=date(2026, 1, 15))
        html = render_html_report(report, [], [detail])
        assert "Section B" in html
        assert "MSFT" in html
        assert "IN-MOMENTUM" in html
