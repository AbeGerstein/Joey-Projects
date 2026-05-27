"""Sector indicators per DWA's 4-factor framework.

Per Dorsey Wright methodology, a sector's "Favored / Average / Unfavored"
status is derived from FOUR breadth indicators (not just one). Each is a
percentage of sector members satisfying a condition:

  BP  — % of sector stocks currently on a P&F buy signal.
  RSX — % of sector stocks whose RS-vs-market chart is in a column of X's.
  RSP — % of sector stocks whose RS-vs-market chart is on a buy signal.
  PT  — % of sector stocks above their bullish support trendline.

DWA classifies each indicator as "positive" or "negative" based on the
indicator's own P&F chart column direction. Building a daily P&F chart
of each indicator across history is a future enhancement; this v1 uses
a 50% threshold as a pragmatic proxy:

  positive = indicator > 50%

A sector with **3 or 4 positive** = **Favored**.
A sector with **2 positive** = **Average**.
A sector with **0 or 1 positive** = **Unfavored**.

This matches the published DWA classification (see Phase C of the
checklist rework spec).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pnf_bot.scoring.stock_state import StockState

SectorClassification = Literal["favored", "average", "unfavored"]

DEFAULT_POSITIVE_THRESHOLD_PCT = Decimal("50")


@dataclass(frozen=True)
class SectorIndicators:
    """The 4 breadth percentages and the derived classification for one sector."""

    sector: str
    member_count: int
    bp_pct: Decimal      # % on P&F buy signal
    rsx_pct: Decimal     # % whose RS-vs-market chart is in column of X's
    rsp_pct: Decimal     # % whose RS-vs-market chart is on a buy signal
    pt_pct: Decimal      # % above bullish support
    positive_count: int  # 0..4
    classification: SectorClassification


def compute_sector_indicators(
    sector: str,
    members: Iterable[StockState],
    positive_threshold_pct: Decimal = DEFAULT_POSITIVE_THRESHOLD_PCT,
) -> SectorIndicators:
    """Compute the 4 indicators and classification for one sector.

    `members` is the list of StockState objects for tickers in this sector.
    If the sector has zero members, returns an "unfavored" classification
    with zeros across the board (defensive).
    """
    member_list = list(members)
    n = len(member_list)
    if n == 0:
        return SectorIndicators(
            sector=sector,
            member_count=0,
            bp_pct=Decimal("0"),
            rsx_pct=Decimal("0"),
            rsp_pct=Decimal("0"),
            pt_pct=Decimal("0"),
            positive_count=0,
            classification="unfavored",
        )

    bp_count = sum(1 for s in member_list if s.is_on_price_buy_signal)
    rsx_count = sum(1 for s in member_list if s.rs_vs_market_current_x)
    rsp_count = sum(1 for s in member_list if s.is_on_rs_vs_market_buy_signal)
    pt_count = sum(1 for s in member_list if s.above_bullish_support)

    bp = Decimal(bp_count) / Decimal(n) * Decimal("100")
    rsx = Decimal(rsx_count) / Decimal(n) * Decimal("100")
    rsp = Decimal(rsp_count) / Decimal(n) * Decimal("100")
    pt = Decimal(pt_count) / Decimal(n) * Decimal("100")

    positives = sum(1 for v in (bp, rsx, rsp, pt) if v > positive_threshold_pct)
    if positives >= 3:
        cls: SectorClassification = "favored"
    elif positives == 2:
        cls = "average"
    else:
        cls = "unfavored"

    return SectorIndicators(
        sector=sector,
        member_count=n,
        bp_pct=bp.quantize(Decimal("0.1")),
        rsx_pct=rsx.quantize(Decimal("0.1")),
        rsp_pct=rsp.quantize(Decimal("0.1")),
        pt_pct=pt.quantize(Decimal("0.1")),
        positive_count=positives,
        classification=cls,
    )


def classify_all_sectors(
    stocks: Iterable[StockState],
    positive_threshold_pct: Decimal = DEFAULT_POSITIVE_THRESHOLD_PCT,
) -> dict[str, SectorIndicators]:
    """Group stocks by sector and compute indicators for every sector.

    Stocks with `sector=None` are aggregated into a synthetic "Unclassified"
    bucket so they still participate in downstream filters (though the
    Favored-sector weight will naturally exclude them).
    """
    by_sector: dict[str, list[StockState]] = {}
    for s in stocks:
        key = s.sector or "Unclassified"
        by_sector.setdefault(key, []).append(s)
    return {
        sector: compute_sector_indicators(sector, members, positive_threshold_pct)
        for sector, members in by_sector.items()
    }


def is_favored(indicators: SectorIndicators | None) -> bool:
    """Convenience predicate used by the checklist ranker's W4 weight."""
    if indicators is None:
        return False
    return indicators.classification == "favored"
