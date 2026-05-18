"""Phase 4D — backtest harness.

Replays the screener over historical dates and measures forward returns
of its top-K picks. Used to:
- Validate the methodology has predictive power before deploying live
- Tune composite weights against empirical performance
- Surface bugs in pattern detectors that synthetic tests miss

The harness is data-vendor-agnostic — it operates on dicts of
{symbol: pandas.DataFrame} where the DataFrames are full historical
OHLC. In production these come from Norgate (per Phase 1); in tests
they're synthetic.

Public API:
    from pnf_bot.backtest import (
        BacktestConfig, BacktestResult, BacktestPick,
        run_backtest,
    )
"""

from pnf_bot.backtest.harness import (
    BacktestConfig,
    BacktestPick,
    BacktestResult,
    run_backtest,
)
from pnf_bot.backtest.metrics import (
    HorizonMetrics,
    PerformanceMetrics,
    compute_metrics,
    forward_return,
)

__all__ = [
    "BacktestConfig",
    "BacktestPick",
    "BacktestResult",
    "HorizonMetrics",
    "PerformanceMetrics",
    "compute_metrics",
    "forward_return",
    "run_backtest",
]
