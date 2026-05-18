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
from pnf_bot.pnf.bpi import (
    BPI_BOX_SIZE,
    BPI_HIGH_RISK_LEVEL,
    BPI_LOW_RISK_LEVEL,
    BPI_REVERSAL,
    BpiPoint,
    BpiState,
    SignalPosture,
    classify_bpi_state,
    compute_bpi,
    compute_bpi_with_breakdown,
    construct_bpi_chart,
    current_signal_posture,
)
from pnf_bot.pnf.chart import construct_chart
from pnf_bot.pnf.posture import StockPosture, evaluate_stock_posture
from pnf_bot.pnf.rs import (
    FUND_RS_BOX_PCT,
    STOCK_RS_BOX_PCT,
    RSSignalStatus,
    compute_rs_ohlc,
    construct_rs_chart,
    is_rs_negative_trend,
    is_rs_positive_trend,
    rs_signal_status,
)
from pnf_bot.pnf.signals import (
    Signal,
    SignalDirection,
    SignalType,
    detect_signals,
    latest_signal,
)
from pnf_bot.pnf.trendlines import (
    Trendline,
    TrendlineType,
    boxes_above_bullish_support,
    boxes_below_bearish_resistance,
    find_bearish_resistance_line,
    find_bullish_support_line,
    is_above_bullish_support,
    is_below_bearish_resistance,
)
from pnf_bot.pnf.types import Column, ColumnType, PnFChart

__all__ = [
    "BPI_BOX_SIZE",
    "BPI_HIGH_RISK_LEVEL",
    "BPI_LOW_RISK_LEVEL",
    "BPI_REVERSAL",
    "BoxScaling",
    "BpiPoint",
    "BpiState",
    "Column",
    "ColumnType",
    "FUND_RS_BOX_PCT",
    "PercentageScaling",
    "PnFChart",
    "RSSignalStatus",
    "STOCK_RS_BOX_PCT",
    "Signal",
    "SignalDirection",
    "SignalPosture",
    "SignalType",
    "StockPosture",
    "TraditionalScaling",
    "Trendline",
    "TrendlineType",
    "boxes_above_bullish_support",
    "boxes_below_bearish_resistance",
    "classify_bpi_state",
    "compute_bpi",
    "compute_bpi_with_breakdown",
    "compute_rs_ohlc",
    "construct_bpi_chart",
    "construct_chart",
    "construct_rs_chart",
    "current_signal_posture",
    "detect_signals",
    "evaluate_stock_posture",
    "find_bearish_resistance_line",
    "find_bullish_support_line",
    "is_above_bullish_support",
    "is_below_bearish_resistance",
    "is_rs_negative_trend",
    "is_rs_positive_trend",
    "latest_signal",
    "rs_signal_status",
]
