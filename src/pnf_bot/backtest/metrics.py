"""Backtest performance metrics.

Computes the standard set of measures the methodology doc calls out:
- Hit rate (fraction of picks with positive forward returns)
- Average winner / average loser
- Maximum drawdown across the equity curve
- Sharpe-like ratio (annualized mean / annualized stdev)

All operate on per-pick forward returns. Multi-horizon variants
return metrics at 1/3/6/12-month forward windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

# Standard forward-return horizons for the backtest
DEFAULT_HORIZONS_TRADING_DAYS = (21, 63, 126, 252)  # ~1m, 3m, 6m, 12m


@dataclass(frozen=True)
class HorizonMetrics:
    """Performance metrics at one forward horizon."""

    horizon_label: str  # e.g., "1m", "3m"
    horizon_days: int
    n_picks: int
    hit_rate: float       # fraction with positive return
    avg_winner: float     # average return among picks with > 0 return
    avg_loser: float      # average return among picks with <= 0 return
    avg_return: float     # mean of all returns
    max_drawdown: float   # largest peak-to-trough drawdown in the equity curve


@dataclass(frozen=True)
class PerformanceMetrics:
    """Aggregate backtest performance across all horizons."""

    n_total_picks: int
    horizons: tuple[HorizonMetrics, ...]


# ---------------------------------------------------------------------------
# Forward return calculation
# ---------------------------------------------------------------------------


def forward_return(
    ohlc: pd.DataFrame,
    entry_date: date,
    horizon_trading_days: int,
) -> float | None:
    """Return the forward return of a position entered at the close of
    `entry_date` and exited `horizon_trading_days` trading days later.

    Uses the close-to-close return. Returns None if entry_date is not in
    the data OR if there are fewer than horizon_trading_days bars after
    entry_date (e.g., near the end of history).
    """
    if "close" not in ohlc.columns:
        return None
    # Find the entry bar
    df = ohlc.sort_index()
    # Convert pandas Timestamp index to date for comparison
    candidate_dates = [
        idx.date() if hasattr(idx, "date") else idx for idx in df.index
    ]
    try:
        entry_idx = candidate_dates.index(entry_date)
    except ValueError:
        return None
    exit_idx = entry_idx + horizon_trading_days
    if exit_idx >= len(df):
        return None
    entry_price = float(df.iloc[entry_idx]["close"])
    exit_price = float(df.iloc[exit_idx]["close"])
    if entry_price <= 0:
        return None
    return (exit_price - entry_price) / entry_price


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


def compute_metrics(
    returns_by_horizon: dict[int, list[float]],
) -> PerformanceMetrics:
    """Compute aggregate metrics from a dict {horizon_days: [returns]}.

    Each list contains the forward returns of every pick at that horizon.
    Returns the structured PerformanceMetrics record consumed by the
    backtest report.
    """
    horizons: list[HorizonMetrics] = []
    total_picks = 0
    for h_days, returns in sorted(returns_by_horizon.items()):
        if not returns:
            horizons.append(_empty_horizon(h_days))
            continue
        winners = [r for r in returns if r > 0]
        losers = [r for r in returns if r <= 0]
        hit_rate = len(winners) / len(returns)
        avg_winner = sum(winners) / len(winners) if winners else 0.0
        avg_loser = sum(losers) / len(losers) if losers else 0.0
        avg_return = sum(returns) / len(returns)
        max_dd = _max_drawdown(returns)
        horizons.append(
            HorizonMetrics(
                horizon_label=_horizon_label(h_days),
                horizon_days=h_days,
                n_picks=len(returns),
                hit_rate=hit_rate,
                avg_winner=avg_winner,
                avg_loser=avg_loser,
                avg_return=avg_return,
                max_drawdown=max_dd,
            )
        )
        total_picks = max(total_picks, len(returns))
    return PerformanceMetrics(n_total_picks=total_picks, horizons=tuple(horizons))


def _max_drawdown(returns: list[float]) -> float:
    """Compute the largest peak-to-trough drawdown of a returns series.

    Treats each return as a sequential portfolio P&L event. Returns 0
    for an empty input or a series with no drawdown.
    """
    if not returns:
        return 0.0
    cumulative = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        cumulative *= 1.0 + r
        peak = max(peak, cumulative)
        dd = (cumulative - peak) / peak if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _horizon_label(days: int) -> str:
    if days <= 30:
        return f"{round(days / 21)}m" if days >= 15 else f"{days}d"
    months = round(days / 21)
    return f"{months}m"


def _empty_horizon(days: int) -> HorizonMetrics:
    return HorizonMetrics(
        horizon_label=_horizon_label(days),
        horizon_days=days,
        n_picks=0,
        hit_rate=0.0,
        avg_winner=0.0,
        avg_loser=0.0,
        avg_return=0.0,
        max_drawdown=0.0,
    )
