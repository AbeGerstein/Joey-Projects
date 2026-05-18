"""Weight tuning workflow — evaluate multiple composite-weight configurations
against historical data and identify the best performing setup.

Two usage modes:

1. **Grid search**: provide a WeightSearchSpec with candidate values for
   each weight component, generate the Cartesian product, evaluate each.
   Useful when you have a small set of values to try per component.

2. **Custom configurations**: pass an explicit list of CompositeWeights
   to evaluate. Useful for targeted comparisons or when grid search would
   be combinatorially expensive.

Both produce ranked WeightEvaluation results so the caller can pick the
best for live use.

Out-of-sample validation: `split_dates_train_test` reserves the final
fraction of rebalance dates for a holdout test, preventing the developer
from tuning to noise.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Callable, Literal

import pandas as pd

from pnf_bot.backtest.harness import (
    BacktestConfig,
    BacktestResult,
    run_backtest,
)
from pnf_bot.backtest.metrics import PerformanceMetrics
from pnf_bot.scoring.composite import (
    IN_MOMENTUM_DEFAULT_WEIGHTS,
    PRE_MOMENTUM_DEFAULT_WEIGHTS,
    CompositeWeights,
)


# Type aliases
ObjectiveFunction = Callable[[PerformanceMetrics], float]
SectionLabel = Literal["pre_momentum", "in_momentum"]


@dataclass(frozen=True)
class WeightSearchSpec:
    """Candidate values for each weight component in a grid search."""

    pattern_setup_values: tuple[float, ...] = (0.25, 0.30, 0.35)
    rs_regime_values: tuple[float, ...] = (0.15, 0.20, 0.25)
    sector_tailwind_values: tuple[float, ...] = (0.10, 0.15, 0.20)
    trendline_distance_values: tuple[float, ...] = (0.10, 0.15, 0.20)
    time_in_base_values: tuple[float, ...] = (0.05, 0.10, 0.15)
    ta_score_modifier_values: tuple[float, ...] = (0.05, 0.10, 0.15)


@dataclass(frozen=True)
class WeightEvaluation:
    """One weight configuration's evaluation result."""

    weights: CompositeWeights
    objective_value: float
    metrics: PerformanceMetrics
    section: SectionLabel


@dataclass(frozen=True)
class WeightTuningResult:
    """Aggregate output of a weight-tuning run."""

    section: SectionLabel
    evaluations: tuple[WeightEvaluation, ...]  # sorted by objective_value DESC
    best: WeightEvaluation
    out_of_sample: WeightEvaluation | None = None  # Only set when train/test split applied


# ---------------------------------------------------------------------------
# Default objective function
# ---------------------------------------------------------------------------


def default_objective(metrics: PerformanceMetrics, horizon_label: str = "3m") -> float:
    """Default objective: avg_return × hit_rate + max_drawdown.

    Higher is better. avg_return × hit_rate captures expected value per pick.
    max_drawdown is negative, so adding it penalizes high-drawdown configs.

    Evaluated at the given horizon (default 3m — long enough for P&F moves
    to play out, short enough for sample size).

    Returns -infinity if the horizon has no picks (avoids ranking empty
    configs).
    """
    horizon = next((h for h in metrics.horizons if h.horizon_label == horizon_label), None)
    if horizon is None or horizon.n_picks == 0:
        return float("-inf")
    return horizon.avg_return * horizon.hit_rate + horizon.max_drawdown


# ---------------------------------------------------------------------------
# Grid generation
# ---------------------------------------------------------------------------


def grid_search_configurations(spec: WeightSearchSpec) -> list[CompositeWeights]:
    """Generate every weight combination from a grid spec."""
    combinations = itertools.product(
        spec.pattern_setup_values,
        spec.rs_regime_values,
        spec.sector_tailwind_values,
        spec.trendline_distance_values,
        spec.time_in_base_values,
        spec.ta_score_modifier_values,
    )
    return [
        CompositeWeights(
            pattern_setup=ps,
            rs_regime=rs,
            sector_tailwind=st,
            trendline_distance=td,
            time_in_base=tb,
            ta_score_modifier=tam,
        )
        for (ps, rs, st, td, tb, tam) in combinations
    ]


# ---------------------------------------------------------------------------
# Train/test split for out-of-sample validation
# ---------------------------------------------------------------------------


def split_dates_train_test(
    rebalance_dates: tuple[date, ...],
    test_fraction: float = 0.2,
) -> tuple[tuple[date, ...], tuple[date, ...]]:
    """Split a tuple of rebalance dates into (train_dates, test_dates).

    Reserves the LAST test_fraction of dates for test (chronological split,
    not random). This prevents look-ahead leakage during tuning.

    Returns (train_dates, test_dates). Either can be empty if input is
    too small.
    """
    if not 0.0 <= test_fraction <= 1.0:
        raise ValueError(f"test_fraction must be in [0, 1], got {test_fraction}")
    sorted_dates = tuple(sorted(rebalance_dates))
    n_test = int(round(len(sorted_dates) * test_fraction))
    if n_test == 0 and test_fraction > 0 and sorted_dates:
        n_test = 1  # at least one test date if test_fraction > 0
    if n_test == 0:
        # test_fraction was 0 — return all dates as train, none as test
        return (sorted_dates, ())
    if n_test >= len(sorted_dates):
        return ((), sorted_dates)
    return (sorted_dates[:-n_test], sorted_dates[-n_test:])


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_weight_configurations(
    configurations: list[CompositeWeights],
    backtest_config: BacktestConfig,
    universe_ohlc: dict[str, pd.DataFrame],
    benchmark_ohlc: pd.DataFrame | None = None,
    sector_map: dict[str, str] | None = None,
    section: SectionLabel = "pre_momentum",
    objective: ObjectiveFunction = default_objective,
) -> list[WeightEvaluation]:
    """Run a backtest for each weight configuration. Return ranked results.

    For section="pre_momentum", the weights drive Section A scoring (in-momentum
    weights stay at defaults). For section="in_momentum", vice versa.
    """
    evaluations: list[WeightEvaluation] = []
    for weights in configurations:
        if section == "pre_momentum":
            config = replace(backtest_config, pre_momentum_weights=weights)
        else:
            config = replace(backtest_config, in_momentum_weights=weights)
        result = run_backtest(config, universe_ohlc, benchmark_ohlc, sector_map)
        metrics = (
            result.section_a_metrics if section == "pre_momentum" else result.section_b_metrics
        )
        value = objective(metrics)
        evaluations.append(
            WeightEvaluation(
                weights=weights,
                objective_value=value,
                metrics=metrics,
                section=section,
            )
        )
    evaluations.sort(key=lambda e: e.objective_value, reverse=True)
    return evaluations


# ---------------------------------------------------------------------------
# High-level tuning entry point
# ---------------------------------------------------------------------------


def tune_weights(
    backtest_config: BacktestConfig,
    universe_ohlc: dict[str, pd.DataFrame],
    benchmark_ohlc: pd.DataFrame | None = None,
    sector_map: dict[str, str] | None = None,
    section: SectionLabel = "pre_momentum",
    search_spec: WeightSearchSpec | None = None,
    custom_configurations: list[CompositeWeights] | None = None,
    objective: ObjectiveFunction = default_objective,
    test_fraction: float = 0.2,
) -> WeightTuningResult:
    """Top-level tuning entry point with optional train/test split.

    Either `search_spec` or `custom_configurations` (or both) provide the
    weight configurations to evaluate. With both omitted, evaluates only
    the default weights.

    If `test_fraction` > 0, splits the backtest dates into train/test,
    tunes on train, and reports the best configuration's performance on
    the held-out test set as `out_of_sample`. With `test_fraction` == 0,
    no split is applied and `out_of_sample` is None.
    """
    configs: list[CompositeWeights] = list(custom_configurations or [])
    if search_spec is not None:
        configs.extend(grid_search_configurations(search_spec))
    if not configs:
        configs.append(
            PRE_MOMENTUM_DEFAULT_WEIGHTS
            if section == "pre_momentum"
            else IN_MOMENTUM_DEFAULT_WEIGHTS
        )

    if test_fraction > 0:
        train_dates, test_dates = split_dates_train_test(
            backtest_config.rebalance_dates, test_fraction=test_fraction
        )
        train_config = replace(backtest_config, rebalance_dates=train_dates)
        evaluations = evaluate_weight_configurations(
            configs, train_config, universe_ohlc, benchmark_ohlc, sector_map,
            section=section, objective=objective,
        )
        best = evaluations[0]
        # Re-evaluate the best weights on the held-out test set
        if test_dates:
            test_config = replace(backtest_config, rebalance_dates=test_dates)
            if section == "pre_momentum":
                test_config = replace(test_config, pre_momentum_weights=best.weights)
            else:
                test_config = replace(test_config, in_momentum_weights=best.weights)
            test_result = run_backtest(
                test_config, universe_ohlc, benchmark_ohlc, sector_map
            )
            test_metrics = (
                test_result.section_a_metrics
                if section == "pre_momentum"
                else test_result.section_b_metrics
            )
            oos = WeightEvaluation(
                weights=best.weights,
                objective_value=objective(test_metrics),
                metrics=test_metrics,
                section=section,
            )
        else:
            oos = None
    else:
        evaluations = evaluate_weight_configurations(
            configs, backtest_config, universe_ohlc, benchmark_ohlc, sector_map,
            section=section, objective=objective,
        )
        best = evaluations[0]
        oos = None

    return WeightTuningResult(
        section=section,
        evaluations=tuple(evaluations),
        best=best,
        out_of_sample=oos,
    )
