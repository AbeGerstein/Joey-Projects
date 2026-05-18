"""Tests for the weight tuning workflow."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from pnf_bot.backtest import (
    BacktestConfig,
    HorizonMetrics,
    PerformanceMetrics,
    WeightSearchSpec,
    default_objective,
    evaluate_weight_configurations,
    grid_search_configurations,
    split_dates_train_test,
    tune_weights,
)
from pnf_bot.scoring.composite import CompositeWeights


def _generate_ohlc(start: date, n_days: int, start_price: float, drift: float) -> pd.DataFrame:
    rows = []
    price = start_price
    for i in range(n_days):
        noise = math.sin(i * 0.7) * 0.5
        price += drift + noise
        rows.append({
            "open": price, "high": price + 0.5, "low": price - 0.5,
            "close": price, "volume": 1_000_000,
        })
    return pd.DataFrame(rows, index=[start + timedelta(days=i) for i in range(n_days)])


class TestDefaultObjective:
    def test_higher_avg_return_scores_higher_at_fixed_hit_rate(self) -> None:
        m1 = PerformanceMetrics(
            n_total_picks=10,
            horizons=(HorizonMetrics(
                horizon_label="3m", horizon_days=63, n_picks=10,
                hit_rate=0.6, avg_winner=0.10, avg_loser=-0.05, avg_return=0.04,
                max_drawdown=-0.05,
            ),),
        )
        m2 = PerformanceMetrics(
            n_total_picks=10,
            horizons=(HorizonMetrics(
                horizon_label="3m", horizon_days=63, n_picks=10,
                hit_rate=0.6, avg_winner=0.15, avg_loser=-0.05, avg_return=0.08,
                max_drawdown=-0.05,
            ),),
        )
        assert default_objective(m2) > default_objective(m1)

    def test_returns_negative_infinity_for_empty_horizon(self) -> None:
        m = PerformanceMetrics(
            n_total_picks=0,
            horizons=(HorizonMetrics(
                horizon_label="3m", horizon_days=63, n_picks=0,
                hit_rate=0.0, avg_winner=0.0, avg_loser=0.0, avg_return=0.0,
                max_drawdown=0.0,
            ),),
        )
        assert default_objective(m) == float("-inf")

    def test_drawdown_penalizes(self) -> None:
        base = PerformanceMetrics(
            n_total_picks=10,
            horizons=(HorizonMetrics(
                horizon_label="3m", horizon_days=63, n_picks=10,
                hit_rate=0.6, avg_winner=0.10, avg_loser=-0.05, avg_return=0.04,
                max_drawdown=-0.05,
            ),),
        )
        deep_dd = PerformanceMetrics(
            n_total_picks=10,
            horizons=(HorizonMetrics(
                horizon_label="3m", horizon_days=63, n_picks=10,
                hit_rate=0.6, avg_winner=0.10, avg_loser=-0.05, avg_return=0.04,
                max_drawdown=-0.30,
            ),),
        )
        assert default_objective(deep_dd) < default_objective(base)


class TestGridSearch:
    def test_grid_size_equals_cartesian_product(self) -> None:
        spec = WeightSearchSpec(
            pattern_setup_values=(0.25, 0.30),
            rs_regime_values=(0.15, 0.20),
            sector_tailwind_values=(0.10,),
            trendline_distance_values=(0.10,),
            time_in_base_values=(0.05,),
            ta_score_modifier_values=(0.10,),
        )
        configs = grid_search_configurations(spec)
        assert len(configs) == 2 * 2 * 1 * 1 * 1 * 1  # = 4

    def test_default_spec_produces_3_to_the_6_combinations(self) -> None:
        configs = grid_search_configurations(WeightSearchSpec())
        assert len(configs) == 3 ** 6  # = 729

    def test_each_config_is_valid_composite_weights(self) -> None:
        spec = WeightSearchSpec(
            pattern_setup_values=(0.30,),
            rs_regime_values=(0.20,),
            sector_tailwind_values=(0.15,),
            trendline_distance_values=(0.15,),
            time_in_base_values=(0.10,),
            ta_score_modifier_values=(0.10,),
        )
        configs = grid_search_configurations(spec)
        assert len(configs) == 1
        assert configs[0].pattern_setup == 0.30
        assert configs[0].ta_score_modifier == 0.10


class TestTrainTestSplit:
    def test_basic_split(self) -> None:
        dates = tuple(date(2026, 1, 1) + timedelta(days=i * 30) for i in range(10))
        train, test = split_dates_train_test(dates, test_fraction=0.2)
        assert len(train) == 8
        assert len(test) == 2
        assert train[-1] < test[0]  # chronological order preserved

    def test_no_split_when_fraction_is_zero(self) -> None:
        dates = tuple(date(2026, 1, 1) + timedelta(days=i * 30) for i in range(5))
        train, test = split_dates_train_test(dates, test_fraction=0.0)
        assert train == dates
        assert test == ()

    def test_small_input_still_reserves_one_for_test(self) -> None:
        dates = (date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1))
        train, test = split_dates_train_test(dates, test_fraction=0.1)
        # 3 × 0.1 = 0.3, rounds to 0 — but with test_fraction > 0 we force at least 1
        assert len(test) == 1

    def test_fraction_out_of_bounds_raises(self) -> None:
        dates = (date(2026, 1, 1), date(2026, 2, 1))
        with pytest.raises(ValueError, match="test_fraction"):
            split_dates_train_test(dates, test_fraction=1.5)


class TestEvaluateWeightConfigurations:
    def test_returns_ranked_results(self) -> None:
        """Even on a small synthetic universe, eval should produce ranked output."""
        ohlc = _generate_ohlc(date(2026, 1, 5), 200, start_price=50.0, drift=0.05)
        config = BacktestConfig(
            rebalance_dates=(date(2026, 5, 1),),
            section_a_top_n=5,
            section_b_top_n=5,
        )
        weights_list = [
            CompositeWeights(pattern_setup=0.30, rs_regime=0.20),
            CompositeWeights(pattern_setup=0.35, rs_regime=0.15),
        ]
        evaluations = evaluate_weight_configurations(
            weights_list, config, universe_ohlc={"TEST": ohlc},
        )
        assert len(evaluations) == 2
        # Sorted by objective_value descending
        assert evaluations[0].objective_value >= evaluations[1].objective_value

    def test_in_momentum_section(self) -> None:
        ohlc = _generate_ohlc(date(2026, 1, 5), 200, start_price=50.0, drift=0.05)
        config = BacktestConfig(rebalance_dates=(date(2026, 5, 1),))
        evaluations = evaluate_weight_configurations(
            [CompositeWeights()], config, universe_ohlc={"TEST": ohlc},
            section="in_momentum",
        )
        assert all(e.section == "in_momentum" for e in evaluations)


class TestTuneWeights:
    def test_default_config_runs_without_search(self) -> None:
        """Calling tune_weights with no search spec just evaluates defaults."""
        ohlc = _generate_ohlc(date(2026, 1, 5), 200, start_price=50.0, drift=0.05)
        config = BacktestConfig(
            rebalance_dates=(date(2026, 4, 1), date(2026, 5, 1), date(2026, 6, 1),),
        )
        result = tune_weights(
            config, universe_ohlc={"TEST": ohlc},
            test_fraction=0.0,
        )
        assert len(result.evaluations) == 1
        assert result.out_of_sample is None

    def test_train_test_split_applied(self) -> None:
        ohlc = _generate_ohlc(date(2026, 1, 5), 400, start_price=50.0, drift=0.05)
        config = BacktestConfig(
            rebalance_dates=tuple(
                date(2026, 1, 5) + timedelta(days=i * 30) for i in range(10)
            ),
        )
        result = tune_weights(
            config, universe_ohlc={"TEST": ohlc},
            test_fraction=0.2,
        )
        # When train/test split is applied, out_of_sample should be populated
        # (may have -inf objective if no test-period picks materialize, but
        # the evaluation object exists)
        assert result.out_of_sample is not None
