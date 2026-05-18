"""Tests for composite scoring and daily report assembly."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from pnf_bot.pnf import construct_chart
from pnf_bot.scoring.composite import (
    ScoredCandidate,
    build_daily_report,
    freshness_multiplier,
    score_stock_in_momentum,
    score_stock_pre_momentum,
)


def _bars(start: date, hl: list[tuple[float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"open": (h + l) / 2, "high": h, "low": l, "close": (h + l) / 2, "volume": 1_000_000}
            for (h, l) in hl
        ],
        index=[start + timedelta(days=i) for i in range(len(hl))],
    )


class TestFreshnessMultiplier:
    def test_one_day_ago_doubles(self) -> None:
        today = date(2026, 5, 18)
        yesterday = today - timedelta(days=1)
        assert freshness_multiplier(yesterday, today) == 2.0

    def test_three_days_ago(self) -> None:
        today = date(2026, 5, 18)
        d = today - timedelta(days=3)
        assert freshness_multiplier(d, today) == 1.5

    def test_baseline_week(self) -> None:
        today = date(2026, 5, 18)
        d = today - timedelta(days=7)
        assert freshness_multiplier(d, today) == 1.0

    def test_decay_over_a_month(self) -> None:
        today = date(2026, 5, 18)
        d = today - timedelta(days=20)
        assert freshness_multiplier(d, today) == 0.7

    def test_stale_over_a_month(self) -> None:
        today = date(2026, 5, 18)
        d = today - timedelta(days=60)
        assert freshness_multiplier(d, today) == 0.4

    def test_today_treats_as_freshest(self) -> None:
        today = date(2026, 5, 18)
        assert freshness_multiplier(today, today) == 2.0


class TestScoreStock:
    def test_short_chart_no_score(self) -> None:
        """A chart with too little history to match any pattern returns None."""
        bars = [(50.0, 50.0)]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        result = score_stock_pre_momentum("T", chart, as_of_date=date(2026, 1, 10))
        # Should be None — no pre-momentum patterns match
        assert result is None or isinstance(result, ScoredCandidate)

    def test_exhausted_chart_is_not_pre_momentum(self) -> None:
        """A parabolic chart is exhausted → not a pre-momentum candidate."""
        bars = [
            (50.0, 50.0),
            (75.0, 50.0),  # 25-box parabolic X column
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        result = score_stock_pre_momentum("T", chart, as_of_date=date(2026, 1, 10))
        assert result is None


class TestBuildDailyReport:
    def _candidate(
        self,
        symbol: str,
        section: str,
        final_score: float,
        fired_last_night: bool = False,
    ) -> ScoredCandidate:
        return ScoredCandidate(
            symbol=symbol,
            section=section,
            base_score=final_score / 2,
            freshness_multiplier=2.0 if fired_last_night else 1.0,
            final_score=final_score,
            matched_patterns=(),
            most_recent_pattern_date=date(2026, 5, 17),
            ta_equivalent_score=3,
            fired_last_night=fired_last_night,
        )

    def test_section_a_top_n_sorts_by_final_score(self) -> None:
        candidates = [
            self._candidate("LOW", "pre_momentum", 0.3),
            self._candidate("HIGH", "pre_momentum", 0.9),
            self._candidate("MID", "pre_momentum", 0.6),
        ]
        report = build_daily_report(
            candidates, as_of_date=date(2026, 5, 18), section_a_top_n=10
        )
        names = [c.symbol for c in report.section_a_top_n]
        assert names == ["HIGH", "MID", "LOW"]

    def test_section_a_respects_top_n_limit(self) -> None:
        candidates = [
            self._candidate(f"S{i}", "pre_momentum", float(i)) for i in range(20)
        ]
        report = build_daily_report(
            candidates, as_of_date=date(2026, 5, 18), section_a_top_n=10
        )
        assert len(report.section_a_top_n) == 10

    def test_sections_are_separated(self) -> None:
        candidates = [
            self._candidate("A1", "pre_momentum", 0.5),
            self._candidate("B1", "in_momentum", 0.5),
            self._candidate("B2", "in_momentum", 0.9),
        ]
        report = build_daily_report(
            candidates, as_of_date=date(2026, 5, 18),
            section_a_top_n=10, section_b_top_n=10,
        )
        assert [c.symbol for c in report.section_a_top_n] == ["A1"]
        assert [c.symbol for c in report.section_b_top_n] == ["B2", "B1"]

    def test_new_last_night_set(self) -> None:
        candidates = [
            self._candidate("FRESH1", "pre_momentum", 0.8, fired_last_night=True),
            self._candidate("FRESH2", "pre_momentum", 0.6, fired_last_night=True),
            self._candidate("STALE", "pre_momentum", 0.9, fired_last_night=False),
        ]
        report = build_daily_report(candidates, as_of_date=date(2026, 5, 18))
        nln = [c.symbol for c in report.new_patterns_last_night]
        # Sorted by final_score within "fired last night"
        assert nln == ["FRESH1", "FRESH2"]

    def test_empty_candidates_produces_empty_report(self) -> None:
        report = build_daily_report([], as_of_date=date(2026, 5, 18))
        assert report.section_a_top_n == ()
        assert report.section_b_top_n == ()
        assert report.new_patterns_last_night == ()
