"""Tests for the backtest harness and metrics."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from pnf_bot.backtest import (
    BacktestConfig,
    compute_metrics,
    forward_return,
    run_backtest,
)


def _generate_ohlc(
    start: date, n_days: int, start_price: float, daily_drift: float, daily_vol: float = 0.5
) -> pd.DataFrame:
    """Synthetic OHLC for testing — deterministic, drift-and-noise based."""
    rows = []
    price = start_price
    for i in range(n_days):
        # Use deterministic sin-based noise so tests are reproducible
        import math

        noise = math.sin(i * 0.7) * daily_vol
        price += daily_drift + noise
        h = price + 0.5
        l = price - 0.5
        rows.append({
            "open": price,
            "high": h,
            "low": l,
            "close": price,
            "volume": 1_000_000,
        })
    idx = [start + timedelta(days=i) for i in range(n_days)]
    return pd.DataFrame(rows, index=idx)


class TestForwardReturn:
    def test_simple_forward_return(self) -> None:
        """A stock that goes from 100 to 110 in 21 days returns ~10%."""
        df = pd.DataFrame(
            {"open": [100, 105, 110], "high": [101, 106, 111],
             "low": [99, 104, 109], "close": [100, 105, 110],
             "volume": [1, 1, 1]},
            index=[date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)],
        )
        ret = forward_return(df, date(2026, 1, 5), 2)
        # 100 → 110 = 10%
        assert ret is not None
        assert abs(ret - 0.10) < 0.001

    def test_returns_none_if_horizon_exceeds_data(self) -> None:
        df = pd.DataFrame(
            {"close": [100, 105]},
            index=[date(2026, 1, 5), date(2026, 1, 6)],
        )
        # Only 2 bars; ask for 10-day forward — should return None
        assert forward_return(df, date(2026, 1, 5), 10) is None

    def test_returns_none_for_missing_entry_date(self) -> None:
        df = pd.DataFrame(
            {"close": [100, 105]},
            index=[date(2026, 1, 5), date(2026, 1, 6)],
        )
        assert forward_return(df, date(2025, 1, 1), 1) is None


class TestComputeMetrics:
    def test_perfect_winners(self) -> None:
        metrics = compute_metrics({21: [0.05, 0.10, 0.03, 0.08, 0.15]})
        h = metrics.horizons[0]
        assert h.hit_rate == 1.0
        assert h.n_picks == 5
        assert h.avg_winner > 0
        assert h.avg_loser == 0.0

    def test_mixed_winners_losers(self) -> None:
        metrics = compute_metrics({21: [0.10, -0.05, 0.20, -0.10]})
        h = metrics.horizons[0]
        assert h.hit_rate == 0.5  # 2 of 4 positive
        assert h.avg_winner > 0
        assert h.avg_loser < 0

    def test_empty_horizon(self) -> None:
        metrics = compute_metrics({21: []})
        h = metrics.horizons[0]
        assert h.n_picks == 0
        assert h.hit_rate == 0.0

    def test_drawdown_basic(self) -> None:
        """A sequence with a big loser should show a negative max_drawdown."""
        metrics = compute_metrics({21: [0.10, 0.10, -0.50, 0.10]})
        h = metrics.horizons[0]
        assert h.max_drawdown < 0  # drawdown is signed (negative)


class TestBacktestHarness:
    def test_empty_universe_runs_without_crash(self) -> None:
        """An empty universe produces a BacktestResult with no picks."""
        config = BacktestConfig(rebalance_dates=(date(2026, 1, 10),))
        result = run_backtest(config, universe_ohlc={})
        assert result.n_rebalances == 1
        assert len(result.picks) == 0

    def test_single_symbol_universe(self) -> None:
        """A universe of one symbol runs cleanly; outcomes depend on synthetic data."""
        sym_ohlc = _generate_ohlc(date(2026, 1, 5), 300, start_price=50.0, daily_drift=0.05)
        config = BacktestConfig(
            rebalance_dates=(date(2026, 6, 1),),
            section_a_top_n=5,
            section_b_top_n=5,
        )
        result = run_backtest(config, universe_ohlc={"TEST": sym_ohlc})
        # Should not crash; picks may be empty if no patterns match
        assert result.n_rebalances == 1
        assert isinstance(result.picks, tuple)

    def test_multi_date_backtest_runs(self) -> None:
        """A backtest with multiple rebalance dates aggregates picks."""
        sym_ohlc = _generate_ohlc(date(2026, 1, 5), 300, start_price=50.0, daily_drift=0.05)
        config = BacktestConfig(
            rebalance_dates=(date(2026, 4, 1), date(2026, 6, 1), date(2026, 8, 1)),
        )
        result = run_backtest(config, universe_ohlc={"TEST": sym_ohlc})
        assert result.n_rebalances == 3
