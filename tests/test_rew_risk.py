"""Tests for the RS-chart Rew/Risk ratio."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pnf_bot.pnf.types import Column, PnFChart
from pnf_bot.scoring.rew_risk import compute_rs_rew_risk


def _box(box: str = "1") -> Decimal:
    return Decimal(box)


def _col(t: str, top: str, bot: str, start: str = "2026-01-05", end: str = "2026-01-10",
         box: str = "1") -> Column:
    return Column(
        type=t,
        top=Decimal(top),
        bottom=Decimal(bot),
        box_size=Decimal(box),
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end),
    )


class TestRewRisk:
    def test_returns_none_for_no_chart(self) -> None:
        assert compute_rs_rew_risk(None) is None

    def test_returns_none_for_empty_chart(self) -> None:
        chart = PnFChart(symbol="T", columns=(), box_scaling_label="traditional")
        assert compute_rs_rew_risk(chart) is None

    def test_returns_none_when_at_all_time_high(self) -> None:
        """If current X col is the highest in the chart, there is no overhead
        resistance — Rew/Risk cannot be computed."""
        cols = (
            _col("X", "50", "45", "2026-01-05", "2026-01-08"),
            _col("O", "49", "44", "2026-01-09", "2026-01-12"),
            _col("X", "60", "45", "2026-01-13", "2026-01-20"),  # current at chart high
        )
        chart = PnFChart(symbol="T", columns=cols, box_scaling_label="traditional")
        assert compute_rs_rew_risk(chart) is None

    def test_computes_ratio_with_overhead_and_support(self) -> None:
        """Current at 50 — both prior X tops (55 and 60) qualify as overhead;
        nearest is 55. BSL anchored at lowest-O + 1 column projects upward 1
        box per column to give the support level at current.
        """
        cols = (
            _col("X", "55", "40", "2026-01-01", "2026-01-05"),   # also overhead (top 55)
            _col("O", "54", "30", "2026-01-06", "2026-01-10"),   # lowest O — BSL anchor
            _col("X", "60", "31", "2026-01-11", "2026-01-15"),   # overhead at 60
            _col("O", "59", "45", "2026-01-16", "2026-01-20"),
            _col("X", "50", "46", "2026-01-21", "2026-01-25"),   # current
        )
        chart = PnFChart(symbol="T", columns=cols, box_scaling_label="traditional")
        rr = compute_rs_rew_risk(chart)
        # Reward = min(55, 60) - 50 = 5
        # BSL anchored at col 2 (lowest_o_idx + 1 = 1+1), anchor_price = 30 + 1 = 31.
        # BSL at col 4: 31 + (4-2)*1 = 33. Risk = 50 - 33 = 17. Ratio = 5/17 ≈ 0.29.
        assert rr is not None
        assert Decimal("0.20") <= rr <= Decimal("0.40")
