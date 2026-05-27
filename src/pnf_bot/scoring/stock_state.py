"""Per-stock snapshot used by the checklist ranker and sector aggregators.

The daily-run pipeline computes a StockState for every active ticker:
price chart, RS chart, latest signals, TA composite, BSL state. All
downstream scoring modules (sector indicators, intra-sector rank, the
checklist ranker itself) consume StockState rather than re-computing
from raw OHLC.

This avoids the O(N) re-fetch / re-chart cost in every consumer.
"""

from __future__ import annotations

from dataclasses import dataclass

from pnf_bot.pnf.signals import Signal
from pnf_bot.pnf.types import PnFChart


@dataclass(frozen=True)
class StockState:
    """All per-stock state needed by the checklist ranker and aggregators."""

    symbol: str
    sector: str | None
    price_chart: PnFChart
    rs_chart_vs_market: PnFChart | None
    latest_price_signal: Signal | None
    latest_rs_vs_market_signal: Signal | None
    ta_score: int  # 0-5
    above_bullish_support: bool
    # Filled in by Phase D when sector indices are built:
    rs_chart_vs_sector: PnFChart | None = None
    latest_rs_vs_sector_signal: Signal | None = None

    @property
    def is_on_price_buy_signal(self) -> bool:
        s = self.latest_price_signal
        return s is not None and s.is_bullish

    @property
    def rs_vs_market_current_x(self) -> bool:
        """RS-vs-market chart is currently in a column of X's (rising)."""
        rs = self.rs_chart_vs_market
        if rs is None or not rs.columns:
            return False
        return rs.columns[-1].type == "X"

    @property
    def is_on_rs_vs_market_buy_signal(self) -> bool:
        s = self.latest_rs_vs_market_signal
        return s is not None and s.is_bullish
