"""Point & Figure analysis engine.

Implements Dorsey's P&F charting conventions from scratch in Python:
- Box scaling: traditional price-tiered (for price charts) and percentage (for RS charts)
- Chart construction: the high/low method following Dorsey's rules
- Signal detection: double top/bottom, triple top/bottom, catapults, triangles, long tails (future)
- Trendlines: 45° bullish support and bearish resistance (future)

See docs/methodology/point-and-figure.md for the methodology this implements.

Public API:
    from pnf_bot.pnf import (
        TraditionalScaling, PercentageScaling,
        Column, PnFChart, ColumnType,
        construct_chart,
    )
"""

from pnf_bot.pnf.box_scaling import (
    BoxScaling,
    PercentageScaling,
    TraditionalScaling,
)
from pnf_bot.pnf.chart import construct_chart
from pnf_bot.pnf.signals import (
    Signal,
    SignalDirection,
    SignalType,
    detect_signals,
    latest_signal,
)
from pnf_bot.pnf.types import Column, ColumnType, PnFChart

__all__ = [
    "BoxScaling",
    "Column",
    "ColumnType",
    "PercentageScaling",
    "PnFChart",
    "Signal",
    "SignalDirection",
    "SignalType",
    "TraditionalScaling",
    "construct_chart",
    "detect_signals",
    "latest_signal",
]
