"""Single-stock posture summary — the per-stock record consumed by scoring.

Bundles every dimension the Phase 4 scoring layer needs:
- P&F state: signal posture, current signal, distance to next signal
- Trend posture: above/below trendlines, distance from each
- RS state: signal posture, trend posture
- Sector context (looked up by the caller, attached here)

This is the canonical record that flows from the P&F engine into the
pre-momentum and in-momentum scorers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pnf_bot.pnf.bpi import SignalPosture, current_signal_posture
from pnf_bot.pnf.rs import RSSignalStatus, is_rs_positive_trend, rs_signal_status
from pnf_bot.pnf.signals import Signal, latest_signal
from pnf_bot.pnf.trendlines import (
    boxes_above_bullish_support,
    boxes_below_bearish_resistance,
    is_above_bullish_support,
    is_below_bearish_resistance,
)
from pnf_bot.pnf.types import PnFChart


@dataclass(frozen=True)
class StockPosture:
    """A complete posture record for a single stock, evaluated as of one date.

    All fields are computed deterministically from the chart inputs. This
    record is what the scoring layer consumes.
    """

    symbol: str
    as_of_date: date

    # P&F price chart state
    price_signal_posture: SignalPosture  # buy / sell / unknown
    most_recent_signal: Signal | None
    is_above_bullish_support: bool
    is_below_bearish_resistance: bool
    boxes_above_support: int
    boxes_below_resistance: int

    # Relative Strength state
    rs_signal_status: RSSignalStatus  # buy / sell / none
    rs_positive_trend: bool

    # Sector context (attached by the caller)
    sector: str | None = None
    sector_bpi: Decimal | None = None
    sector_bpi_state: str | None = None  # one of the BpiState values


def evaluate_stock_posture(
    symbol: str,
    price_chart: PnFChart,
    rs_chart: PnFChart | None = None,
    as_of_date: date | None = None,
    sector: str | None = None,
    sector_bpi: Decimal | None = None,
    sector_bpi_state: str | None = None,
) -> StockPosture:
    """Compute the full posture record for one stock.

    `rs_chart` is optional — if absent, RS fields are reported as "none"/False.
    `as_of_date` defaults to today.
    Sector context fields are passed through unchanged (the caller looks up
    sector BPIs from the BPI engine and attaches them).
    """
    price_signal = current_signal_posture(price_chart)
    most_recent = latest_signal(price_chart)

    if rs_chart is not None:
        rs_status = rs_signal_status(rs_chart)
        rs_pos = is_rs_positive_trend(rs_chart)
    else:
        rs_status = "none"
        rs_pos = False

    return StockPosture(
        symbol=symbol,
        as_of_date=as_of_date or date.today(),
        price_signal_posture=price_signal,
        most_recent_signal=most_recent,
        is_above_bullish_support=is_above_bullish_support(price_chart),
        is_below_bearish_resistance=is_below_bearish_resistance(price_chart),
        boxes_above_support=boxes_above_bullish_support(price_chart),
        boxes_below_resistance=boxes_below_bearish_resistance(price_chart),
        rs_signal_status=rs_status,
        rs_positive_trend=rs_pos,
        sector=sector,
        sector_bpi=sector_bpi,
        sector_bpi_state=sector_bpi_state,
    )
