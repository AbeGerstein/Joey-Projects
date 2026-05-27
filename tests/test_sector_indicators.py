"""Tests for sector indicator aggregation and classification."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pnf_bot.pnf.signals import Signal
from pnf_bot.pnf.types import Column, PnFChart
from pnf_bot.scoring.sector_indicators import (
    classify_all_sectors,
    compute_sector_indicators,
    is_favored,
)
from pnf_bot.scoring.stock_state import StockState


def _chart(last_col_type: str = "X") -> PnFChart:
    """Minimal chart with a single column of the requested type."""
    col = Column(
        type=last_col_type,
        top=Decimal("50"),
        bottom=Decimal("45"),
        box_size=Decimal("1"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
    )
    return PnFChart(symbol="T", columns=(col,), box_scaling_label="traditional")


def _sig(bullish: bool) -> Signal:
    return Signal(
        type="double_top" if bullish else "double_bottom",
        direction="bullish" if bullish else "bearish",
        column_index=0,
        fired_date=date(2026, 1, 10),
        price_level=Decimal("50"),
    )


def _stock(
    symbol: str,
    sector: str | None,
    on_buy: bool,
    rs_current_x: bool,
    rs_on_buy: bool,
    above_bsl: bool,
    ta_score: int = 3,
) -> StockState:
    return StockState(
        symbol=symbol,
        sector=sector,
        price_chart=_chart(),
        rs_chart_vs_market=_chart("X" if rs_current_x else "O"),
        latest_price_signal=_sig(on_buy),
        latest_rs_vs_market_signal=_sig(rs_on_buy),
        ta_score=ta_score,
        above_bullish_support=above_bsl,
    )


class TestComputeSectorIndicators:
    def test_empty_sector_returns_unfavored_zeros(self) -> None:
        ind = compute_sector_indicators("Tech", [])
        assert ind.member_count == 0
        assert ind.bp_pct == Decimal("0")
        assert ind.classification == "unfavored"

    def test_all_four_indicators_positive_favored(self) -> None:
        """4 stocks, all on every condition → 100% on every indicator → Favored."""
        stocks = [
            _stock("A", "Tech", True, True, True, True),
            _stock("B", "Tech", True, True, True, True),
            _stock("C", "Tech", True, True, True, True),
            _stock("D", "Tech", True, True, True, True),
        ]
        ind = compute_sector_indicators("Tech", stocks)
        assert ind.member_count == 4
        assert ind.bp_pct == Decimal("100.0")
        assert ind.rsx_pct == Decimal("100.0")
        assert ind.rsp_pct == Decimal("100.0")
        assert ind.pt_pct == Decimal("100.0")
        assert ind.positive_count == 4
        assert ind.classification == "favored"

    def test_three_of_four_positive_favored(self) -> None:
        """All on BP/RSX/RSP, none above BSL → 75/75/75/0 → 3 positive → Favored."""
        stocks = [
            _stock("A", "Tech", True, True, True, False),
            _stock("B", "Tech", True, True, True, False),
            _stock("C", "Tech", True, True, True, False),
            _stock("D", "Tech", True, True, True, False),
        ]
        ind = compute_sector_indicators("Tech", stocks)
        assert ind.positive_count == 3
        assert ind.classification == "favored"

    def test_two_positive_average(self) -> None:
        """100% on BP and RSX, 0% on RSP and PT → 2 positive → Average."""
        stocks = [
            _stock("A", "Tech", True, True, False, False),
            _stock("B", "Tech", True, True, False, False),
        ]
        ind = compute_sector_indicators("Tech", stocks)
        assert ind.positive_count == 2
        assert ind.classification == "average"

    def test_one_positive_unfavored(self) -> None:
        stocks = [
            _stock("A", "Tech", True, False, False, False),
            _stock("B", "Tech", True, False, False, False),
        ]
        ind = compute_sector_indicators("Tech", stocks)
        assert ind.positive_count == 1
        assert ind.classification == "unfavored"

    def test_exactly_50_percent_is_not_positive(self) -> None:
        """Threshold is STRICTLY > 50%, so exactly 50% counts as negative."""
        stocks = [
            _stock("A", "Tech", True, True, True, True),
            _stock("B", "Tech", False, False, False, False),
        ]
        ind = compute_sector_indicators("Tech", stocks)
        # 50% on every indicator → 0 positives
        assert ind.bp_pct == Decimal("50.0")
        assert ind.positive_count == 0
        assert ind.classification == "unfavored"


class TestClassifyAllSectors:
    def test_groups_by_sector_field(self) -> None:
        stocks = [
            _stock("A", "Tech", True, True, True, True),
            _stock("B", "Tech", True, True, True, True),
            _stock("C", "Health", False, False, False, False),
            _stock("D", None, True, True, True, True),  # unclassified
        ]
        result = classify_all_sectors(stocks)
        assert "Tech" in result
        assert "Health" in result
        assert "Unclassified" in result
        assert result["Tech"].classification == "favored"
        assert result["Health"].classification == "unfavored"


class TestIsFavored:
    def test_is_favored_true(self) -> None:
        stocks = [_stock("A", "T", True, True, True, True)]
        result = classify_all_sectors(stocks)
        assert is_favored(result["T"]) is True

    def test_is_favored_false_for_average(self) -> None:
        stocks = [
            _stock("A", "T", True, True, False, False),
            _stock("B", "T", True, True, False, False),
        ]
        result = classify_all_sectors(stocks)
        assert is_favored(result["T"]) is False

    def test_is_favored_none(self) -> None:
        assert is_favored(None) is False
