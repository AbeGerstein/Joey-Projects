"""Position-within-sector ranking and weight tiers.

The DWA convention for "top 10% of its sector" is the **Relative Strength
Matrix** rank — a pairwise RS tournament that gives each stock a peer-buy
count. The full Matrix is O(N²) per sector, which is tractable but
expensive on every daily run.

This v1 uses a **TA score proxy**: rank stocks within a sector by their
0–5 technical-attribute score. Ties are broken by which stocks are on a
price-chart buy signal (a heuristic that gives the higher rank to the
stock that's currently moving in the right direction).

The proxy is reasonable because the TA score already encapsulates 4 of
the 5 RS-related conditions the Matrix is measuring (price buy, above
BSL, RS buy, RS positive trend) plus sector BPI. Once the full RS Matrix
is built (later phase), this module switches its ranking source without
changing the weighting tiers below.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from pnf_bot.scoring.stock_state import StockState


@dataclass(frozen=True)
class IntraSectorRank:
    """Position of one stock within its sector (lower percentile = stronger)."""

    symbol: str
    sector: str | None
    rank_position: int      # 1 = strongest in sector
    sector_size: int
    percentile: Decimal     # 0.0 = top of sector, 1.0 = bottom


def rank_within_sectors(stocks: Iterable[StockState]) -> dict[str, IntraSectorRank]:
    """Compute each stock's percentile rank within its sector.

    Stocks are ranked by (-ta_score, -is_on_price_buy_signal). Lower
    percentile = stronger. Stocks with sector=None are ranked together
    in an "Unclassified" group.

    Returns a dict keyed by symbol so the checklist ranker can look up
    each candidate in O(1).
    """
    by_sector: dict[str, list[StockState]] = {}
    for s in stocks:
        key = s.sector or "Unclassified"
        by_sector.setdefault(key, []).append(s)

    result: dict[str, IntraSectorRank] = {}
    for _sector_key, members in by_sector.items():
        # Sort strongest first
        members_sorted = sorted(
            members,
            key=lambda s: (-s.ta_score, 0 if s.is_on_price_buy_signal else 1),
        )
        n = len(members_sorted)
        for idx, s in enumerate(members_sorted):
            position = idx + 1
            percentile = Decimal(idx) / Decimal(max(1, n - 1)) if n > 1 else Decimal("0")
            result[s.symbol] = IntraSectorRank(
                symbol=s.symbol,
                sector=s.sector,
                rank_position=position,
                sector_size=n,
                percentile=percentile.quantize(Decimal("0.001")),
            )
    return result


def intra_sector_weight(
    rank: IntraSectorRank | None,
    max_weight: Decimal = Decimal("1.0"),
) -> Decimal:
    """Convert an intra-sector percentile to a weight contribution.

    Tiers per checklist spec:
        top 10%       (percentile <= 0.10) → most weight (= max_weight)
        10-25%        (0.10 < p <= 0.25)   → 0.60 × max_weight
        25-50%        (0.25 < p <= 0.50)   → 0.30 × max_weight
        > 50%         → 0
    """
    if rank is None:
        return Decimal("0")
    p = rank.percentile
    if p <= Decimal("0.10"):
        return max_weight
    if p <= Decimal("0.25"):
        return max_weight * Decimal("0.60")
    if p <= Decimal("0.50"):
        return max_weight * Decimal("0.30")
    return Decimal("0")
