"""Tests for intra-sector ranking and weight tiers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pnf_bot.pnf.signals import Signal
from pnf_bot.pnf.types import Column, PnFChart
from pnf_bot.scoring.intra_sector_rank import (
    IntraSectorRank,
    intra_sector_weight,
    rank_within_sectors,
)
from pnf_bot.scoring.stock_state import StockState


def _chart() -> PnFChart:
    col = Column(
        type="X",
        top=Decimal("50"),
        bottom=Decimal("45"),
        box_size=Decimal("1"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
    )
    return PnFChart(symbol="T", columns=(col,), box_scaling_label="traditional")


def _stock(symbol: str, sector: str, ta: int, on_buy: bool = True) -> StockState:
    sig = Signal(
        type="double_top",
        direction="bullish" if on_buy else "bearish",
        column_index=0,
        fired_date=date(2026, 1, 10),
        price_level=Decimal("50"),
    )
    return StockState(
        symbol=symbol,
        sector=sector,
        price_chart=_chart(),
        rs_chart_vs_market=_chart(),
        latest_price_signal=sig,
        latest_rs_vs_market_signal=sig,
        ta_score=ta,
        above_bullish_support=True,
    )


class TestRankWithinSectors:
    def test_higher_ta_ranks_first(self) -> None:
        stocks = [
            _stock("LOW", "Tech", ta=2),
            _stock("MID", "Tech", ta=3),
            _stock("HIGH", "Tech", ta=5),
        ]
        ranks = rank_within_sectors(stocks)
        assert ranks["HIGH"].rank_position == 1
        assert ranks["MID"].rank_position == 2
        assert ranks["LOW"].rank_position == 3

    def test_percentile_top_is_zero(self) -> None:
        stocks = [_stock(f"S{i}", "Tech", ta=5 - (i % 6)) for i in range(20)]
        ranks = rank_within_sectors(stocks)
        # The first-ranked (highest TA) stock should have percentile 0.0
        top = min(ranks.values(), key=lambda r: r.rank_position)
        assert top.percentile == Decimal("0.000")

    def test_independent_per_sector(self) -> None:
        """Stocks in different sectors are ranked independently."""
        stocks = [
            _stock("T1", "Tech", ta=5),
            _stock("T2", "Tech", ta=3),
            _stock("H1", "Health", ta=4),
            _stock("H2", "Health", ta=2),
        ]
        ranks = rank_within_sectors(stocks)
        assert ranks["T1"].rank_position == 1
        assert ranks["T2"].rank_position == 2
        assert ranks["H1"].rank_position == 1
        assert ranks["H2"].rank_position == 2

    def test_tiebreak_by_buy_signal(self) -> None:
        """When TA is tied, the stock on a buy signal ranks higher."""
        stocks = [
            _stock("OFF", "Tech", ta=4, on_buy=False),
            _stock("ON", "Tech", ta=4, on_buy=True),
        ]
        ranks = rank_within_sectors(stocks)
        assert ranks["ON"].rank_position == 1
        assert ranks["OFF"].rank_position == 2

    def test_single_member_sector_zero_percentile(self) -> None:
        stocks = [_stock("ONLY", "Niche", ta=3)]
        ranks = rank_within_sectors(stocks)
        assert ranks["ONLY"].percentile == Decimal("0")
        assert ranks["ONLY"].rank_position == 1


class TestIntraSectorWeight:
    def _rank(self, percentile: str) -> IntraSectorRank:
        return IntraSectorRank(
            symbol="X",
            sector="T",
            rank_position=1,
            sector_size=100,
            percentile=Decimal(percentile),
        )

    def test_top_10_pct_gets_max_weight(self) -> None:
        assert intra_sector_weight(self._rank("0.05")) == Decimal("1.0")
        assert intra_sector_weight(self._rank("0.10")) == Decimal("1.0")

    def test_10_to_25_pct_gets_60pct_weight(self) -> None:
        assert intra_sector_weight(self._rank("0.15")) == Decimal("0.6")
        assert intra_sector_weight(self._rank("0.25")) == Decimal("0.6")

    def test_25_to_50_pct_gets_30pct_weight(self) -> None:
        assert intra_sector_weight(self._rank("0.30")) == Decimal("0.3")
        assert intra_sector_weight(self._rank("0.50")) == Decimal("0.3")

    def test_below_50_pct_gets_zero(self) -> None:
        assert intra_sector_weight(self._rank("0.51")) == Decimal("0")
        assert intra_sector_weight(self._rank("0.90")) == Decimal("0")

    def test_none_returns_zero(self) -> None:
        assert intra_sector_weight(None) == Decimal("0")
