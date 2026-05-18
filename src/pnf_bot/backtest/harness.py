"""Backtest harness — replays the screener over historical dates.

The harness walks a configured date range, and at each rebalance date:
1. Builds point-in-time P&F charts using only data up to that date
2. Runs the full scoring pipeline (pre-momentum + in-momentum + anti-patterns)
3. Records the top-K picks per section
4. Measures forward returns at each configured horizon

Returns a BacktestResult with all picks, all forward returns, and a
PerformanceMetrics summary.

Designed for ~6,000-name universes over 5-10 years. Performance: the
expensive operation is chart construction per (symbol, date). The
implementation can be optimized later by incrementally extending charts
rather than reconstructing per-date — for v1 we reconstruct (correct
and simple, slower).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from pnf_bot.backtest.metrics import (
    DEFAULT_HORIZONS_TRADING_DAYS,
    PerformanceMetrics,
    compute_metrics,
    forward_return,
)
from pnf_bot.pnf.chart import construct_chart
from pnf_bot.pnf.rs import construct_rs_chart
from pnf_bot.scoring.composite import (
    IN_MOMENTUM_DEFAULT_WEIGHTS,
    PRE_MOMENTUM_DEFAULT_WEIGHTS,
    CompositeWeights,
    DailyReport,
    ScoredCandidate,
    build_daily_report,
    score_stock_in_momentum,
    score_stock_pre_momentum,
)


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration for one backtest run."""

    rebalance_dates: tuple[date, ...]      # dates on which to run the screener
    section_a_top_n: int = 10
    section_b_top_n: int = 10
    horizons_trading_days: tuple[int, ...] = DEFAULT_HORIZONS_TRADING_DAYS
    pre_momentum_weights: CompositeWeights = field(default=PRE_MOMENTUM_DEFAULT_WEIGHTS)
    in_momentum_weights: CompositeWeights = field(default=IN_MOMENTUM_DEFAULT_WEIGHTS)


@dataclass(frozen=True)
class BacktestPick:
    """One pick made by the screener at a rebalance date, with forward returns."""

    rebalance_date: date
    candidate: ScoredCandidate
    forward_returns: dict[int, float | None]  # horizon_days -> return (or None if unavailable)


@dataclass(frozen=True)
class BacktestResult:
    """Aggregate output of a backtest run."""

    config: BacktestConfig
    n_rebalances: int
    picks: tuple[BacktestPick, ...]
    section_a_metrics: PerformanceMetrics
    section_b_metrics: PerformanceMetrics


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_backtest(
    config: BacktestConfig,
    universe_ohlc: dict[str, pd.DataFrame],
    benchmark_ohlc: pd.DataFrame | None = None,
    sector_map: dict[str, str] | None = None,
) -> BacktestResult:
    """Run a backtest.

    `universe_ohlc` is a dict mapping symbol -> full historical OHLC DataFrame.
    Each DataFrame must be indexed by date and have at least 'high', 'low',
    'close' columns.

    `benchmark_ohlc` is the benchmark for RS calculations (typically RSP).
    If None, RS is disabled.

    `sector_map` is an optional dict mapping symbol -> GICS sector. Used
    for the sector_bpi_state score component (currently passed through as
    static labels; a full sector-BPI-history backtest would require
    computing sector BPI per date, which v1 omits for simplicity).

    Returns a BacktestResult with every pick and aggregate metrics.
    """
    all_picks: list[BacktestPick] = []
    section_a_returns: dict[int, list[float]] = {h: [] for h in config.horizons_trading_days}
    section_b_returns: dict[int, list[float]] = {h: [] for h in config.horizons_trading_days}

    for rebal_date in config.rebalance_dates:
        report = _run_one_rebalance(
            rebal_date=rebal_date,
            universe_ohlc=universe_ohlc,
            benchmark_ohlc=benchmark_ohlc,
            sector_map=sector_map,
            config=config,
        )
        # Record picks + forward returns
        for cand in report.section_a_top_n:
            picks_record = _record_pick(rebal_date, cand, universe_ohlc, config.horizons_trading_days)
            all_picks.append(picks_record)
            for h_days, ret in picks_record.forward_returns.items():
                if ret is not None:
                    section_a_returns[h_days].append(ret)
        for cand in report.section_b_top_n:
            picks_record = _record_pick(rebal_date, cand, universe_ohlc, config.horizons_trading_days)
            all_picks.append(picks_record)
            for h_days, ret in picks_record.forward_returns.items():
                if ret is not None:
                    section_b_returns[h_days].append(ret)

    return BacktestResult(
        config=config,
        n_rebalances=len(config.rebalance_dates),
        picks=tuple(all_picks),
        section_a_metrics=compute_metrics(section_a_returns),
        section_b_metrics=compute_metrics(section_b_returns),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_one_rebalance(
    rebal_date: date,
    universe_ohlc: dict[str, pd.DataFrame],
    benchmark_ohlc: pd.DataFrame | None,
    sector_map: dict[str, str] | None,
    config: BacktestConfig,
) -> DailyReport:
    """Run the full screener for one historical date and return the DailyReport."""
    candidates: list[ScoredCandidate] = []

    # Slice benchmark to the as-of date for RS construction
    bench_slice = (
        _slice_to_date(benchmark_ohlc, rebal_date) if benchmark_ohlc is not None else None
    )

    for symbol, full_ohlc in universe_ohlc.items():
        sliced = _slice_to_date(full_ohlc, rebal_date)
        if sliced.empty:
            continue
        # Need at least a minimal history to detect patterns
        if len(sliced) < 5:
            continue
        try:
            price_chart = construct_chart(symbol, sliced)
        except (ValueError, Exception):  # noqa: BLE001
            continue
        rs_chart = None
        if bench_slice is not None and not bench_slice.empty:
            try:
                rs_chart = construct_rs_chart(symbol, sliced, bench_slice)
            except Exception:  # noqa: BLE001
                rs_chart = None

        # Sector context is intentionally not used in v1 backtest — sector BPI
        # history per-date is not computed (would require an extra inner loop
        # over the entire universe per rebalance date). sector_map is reserved
        # for a future point-in-time sector BPI implementation.
        _ = sector_map.get(symbol) if sector_map else None

        pre = score_stock_pre_momentum(
            symbol, price_chart, rs_chart=rs_chart,
            sector_bpi_state=None,  # v1 backtest does not compute sector BPI history
            as_of_date=rebal_date,
            weights=config.pre_momentum_weights,
        )
        if pre is not None:
            candidates.append(pre)
        in_mom = score_stock_in_momentum(
            symbol, price_chart, rs_chart=rs_chart,
            sector_bpi_state=None,
            as_of_date=rebal_date,
            weights=config.in_momentum_weights,
        )
        if in_mom is not None:
            candidates.append(in_mom)

    return build_daily_report(
        candidates,
        as_of_date=rebal_date,
        section_a_top_n=config.section_a_top_n,
        section_b_top_n=config.section_b_top_n,
    )


def _slice_to_date(ohlc: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Return the subset of ohlc with dates <= as_of."""
    if ohlc.empty:
        return ohlc
    df = ohlc.sort_index()
    mask = pd.Series(
        [_idx_to_date(idx) <= as_of for idx in df.index],
        index=df.index,
    )
    return df[mask]


def _idx_to_date(idx_value) -> date:  # noqa: ANN001
    if hasattr(idx_value, "date"):
        return idx_value.date()
    return idx_value


def _record_pick(
    rebal_date: date,
    candidate: ScoredCandidate,
    universe_ohlc: dict[str, pd.DataFrame],
    horizons: tuple[int, ...],
) -> BacktestPick:
    """Measure forward returns for a single pick at each horizon."""
    ohlc = universe_ohlc.get(candidate.symbol)
    fwd_returns: dict[int, float | None] = {}
    for h in horizons:
        if ohlc is None:
            fwd_returns[h] = None
        else:
            fwd_returns[h] = forward_return(ohlc, rebal_date, h)
    return BacktestPick(
        rebalance_date=rebal_date,
        candidate=candidate,
        forward_returns=fwd_returns,
    )
