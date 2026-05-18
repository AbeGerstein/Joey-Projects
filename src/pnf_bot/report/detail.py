"""Per-stock detail records for the daily report.

For every candidate in Section A or Section B, the report block shows
15 elements (per docs/00-project-outline.md Phase 5). This module
assembles those elements into a structured record the template renders.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pnf_bot.pnf.bpi import BpiState
from pnf_bot.pnf.signals import Signal, detect_signals
from pnf_bot.pnf.trendlines import (
    boxes_above_bullish_support,
    boxes_below_bearish_resistance,
)
from pnf_bot.pnf.types import PnFChart
from pnf_bot.report.charts import render_pnf_chart, render_rs_chart
from pnf_bot.scoring.composite import ScoredCandidate


@dataclass(frozen=True)
class SignalHistoryEntry:
    """One row in the per-stock signal-history breakdown."""

    signal_type: str
    direction: str
    fired_date: date
    price_level: Decimal


@dataclass(frozen=True)
class StockDetailRecord:
    """The 15-element per-stock record rendered by the daily report.

    Built from a ScoredCandidate plus the underlying charts and metadata.
    """

    # 1. Identity
    symbol: str
    company_name: str | None
    sector: str | None
    current_price: Decimal | None

    # 2. Classification
    section: str  # "pre_momentum" or "in_momentum"
    primary_pattern: str

    # 3. Composite score breakdown
    base_score: float
    freshness_multiplier: float
    final_score: float
    fired_last_night: bool

    # 4-5. Chart images (PNG bytes, base64-encoded for HTML embedding)
    pnf_chart_b64: str
    rs_chart_b64: str | None

    # 6-7. Signal state and history
    current_signal: Signal | None
    recent_signals: tuple[SignalHistoryEntry, ...]  # 3-5 most recent

    # 8. Pattern reasoning narrative
    pattern_reasoning: str

    # 9-10. RS and sector context
    rs_signal_status: str  # "buy" / "sell" / "none"
    rs_positive_trend: bool
    sector_bpi_value: Decimal | None
    sector_bpi_state: BpiState | None

    # 11. Trend posture
    above_bullish_support: bool
    boxes_above_support: int
    below_bearish_resistance: bool
    boxes_below_resistance: int

    # 12-13. Suggested entry zone and P&F stop
    suggested_entry: Decimal | None
    suggested_stop: Decimal | None

    # 14. Pre/in-momentum specific notes
    notes: str

    # 15. (Optional) DWA Technical Attributes score from NDWEQTA — unset
    # under the Norgate-only path, populated if/when NDWEQTA is licensed.
    dwa_ta_score: int | None
    internal_ta_score: int


def compile_stock_detail(
    candidate: ScoredCandidate,
    price_chart: PnFChart,
    rs_chart: PnFChart | None = None,
    *,
    company_name: str | None = None,
    sector: str | None = None,
    sector_bpi_value: Decimal | None = None,
    sector_bpi_state: BpiState | None = None,
    dwa_ta_score: int | None = None,
) -> StockDetailRecord:
    """Assemble the full per-stock detail record.

    Renders the P&F chart and (if provided) the RS chart to PNG and
    base64-encodes them for inline HTML embedding.
    """
    pnf_png = render_pnf_chart(price_chart, title=f"{candidate.symbol}  P&F")
    pnf_b64 = base64.b64encode(pnf_png).decode("ascii")
    rs_b64: str | None = None
    if rs_chart is not None and rs_chart.columns:
        rs_png = render_rs_chart(rs_chart)
        rs_b64 = base64.b64encode(rs_png).decode("ascii")

    signals = detect_signals(price_chart)
    current_signal = signals[-1] if signals else None
    recent = tuple(
        SignalHistoryEntry(
            signal_type=s.type,
            direction=s.direction,
            fired_date=s.fired_date,
            price_level=s.price_level,
        )
        for s in signals[-5:]
    )

    # Trend posture
    above_support = boxes_above_bullish_support(price_chart) > 0 or _is_above_support(price_chart)
    below_resistance = boxes_below_bearish_resistance(price_chart) > 0
    boxes_above = boxes_above_bullish_support(price_chart)
    boxes_below = boxes_below_bearish_resistance(price_chart)

    # Suggested entry / stop
    current_col = price_chart.columns[-1] if price_chart.columns else None
    if current_col is not None:
        suggested_entry = current_col.top + current_col.box_size if current_col.type == "X" else current_col.bottom
        # Stop one box below the support line at current column, OR one box below recent low
        suggested_stop = _suggested_stop(price_chart)
        current_price = current_col.top if current_col.type == "X" else current_col.bottom
    else:
        suggested_entry = None
        suggested_stop = None
        current_price = None

    primary = candidate.matched_patterns[0].pattern_type if candidate.matched_patterns else "—"
    reasoning = _build_reasoning(candidate, current_signal)
    notes = _build_notes(candidate, price_chart)

    rs_signal_str = "none"
    rs_pos = False
    if rs_chart is not None:
        from pnf_bot.pnf.rs import is_rs_positive_trend, rs_signal_status

        rs_signal_str = rs_signal_status(rs_chart)
        rs_pos = is_rs_positive_trend(rs_chart)

    return StockDetailRecord(
        symbol=candidate.symbol,
        company_name=company_name,
        sector=sector,
        current_price=current_price,
        section=candidate.section,
        primary_pattern=primary,
        base_score=candidate.base_score,
        freshness_multiplier=candidate.freshness_multiplier,
        final_score=candidate.final_score,
        fired_last_night=candidate.fired_last_night,
        pnf_chart_b64=pnf_b64,
        rs_chart_b64=rs_b64,
        current_signal=current_signal,
        recent_signals=recent,
        pattern_reasoning=reasoning,
        rs_signal_status=rs_signal_str,
        rs_positive_trend=rs_pos,
        sector_bpi_value=sector_bpi_value,
        sector_bpi_state=sector_bpi_state,
        above_bullish_support=above_support,
        boxes_above_support=boxes_above,
        below_bearish_resistance=below_resistance,
        boxes_below_resistance=boxes_below,
        suggested_entry=suggested_entry,
        suggested_stop=suggested_stop,
        notes=notes,
        dwa_ta_score=dwa_ta_score,
        internal_ta_score=candidate.ta_equivalent_score,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_above_support(chart: PnFChart) -> bool:
    from pnf_bot.pnf.trendlines import is_above_bullish_support

    return is_above_bullish_support(chart)


def _suggested_stop(chart: PnFChart) -> Decimal | None:
    """Suggested P&F stop: one box below the bullish support line at the
    current column, OR one box below the most recent O column's bottom
    if no support line exists.
    """
    from pnf_bot.pnf.trendlines import find_bullish_support_line

    line = find_bullish_support_line(chart)
    if line is not None and chart.columns:
        current_idx = len(chart.columns) - 1
        line_price = line.price_at_column(current_idx)
        return line_price - chart.columns[current_idx].box_size
    # Fallback: one box below most recent O bottom
    for col in reversed(chart.columns):
        if col.type == "O":
            return col.bottom - col.box_size
    return None


def _build_reasoning(candidate: ScoredCandidate, current_signal: Signal | None) -> str:
    """Build a one-paragraph human-readable narrative explaining why the
    stock was surfaced.
    """
    parts = []
    if current_signal is not None:
        parts.append(
            f"Currently on a {current_signal.type.replace('_', ' ')} "
            f"signal fired {current_signal.fired_date}"
        )
    for match in candidate.matched_patterns:
        parts.append(match.description)
    if candidate.fired_last_night:
        parts.append("Pattern fired in the most recent trading session.")
    if not parts:
        return "(no narrative available)"
    return " · ".join(parts)


def _build_notes(candidate: ScoredCandidate, chart: PnFChart) -> str:
    """Section-specific notes."""
    if not chart.columns:
        return ""
    cur = chart.columns[-1]
    if candidate.section == "pre_momentum":
        return (
            f"Pre-momentum candidate · time in current column: "
            f"{(cur.end_date - cur.start_date).days} days · "
            f"current column height: {cur.height_boxes} boxes"
        )
    return (
        f"In-momentum candidate · current column has {cur.height_boxes} boxes; "
        f"watch for exhaustion above 15 boxes above support"
    )
