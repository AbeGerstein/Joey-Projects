"""Tests for the checklist ranker."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

from pnf_bot.pnf import construct_chart
from pnf_bot.pnf.signals import latest_signal
from pnf_bot.pnf.trendlines import is_above_bullish_support
from pnf_bot.scoring.checklist import (
    WeightsConfig,
    run_checklist,
)
from pnf_bot.scoring.intra_sector_rank import (
    rank_within_sectors,
)
from pnf_bot.scoring.sector_indicators import (
    classify_all_sectors,
)
from pnf_bot.scoring.stock_state import StockState


def _ohlc(bars: list[tuple[date, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "open": (h + l) / 2,
                "high": h,
                "low": l,
                "close": (h + l) / 2,
                "volume": 1_000_000,
            }
            for (_, h, l) in bars
        ],
        index=[d for (d, _, _) in bars],
    )


def _state(symbol: str, sector: str, bars: list[tuple[date, float, float]],
           ta_score: int = 3) -> StockState:
    """Build a StockState from a synthetic bar series."""
    df = _ohlc(bars)
    chart = construct_chart(symbol, df)
    return StockState(
        symbol=symbol,
        sector=sector,
        price_chart=chart,
        rs_chart_vs_market=chart,  # same chart for tests, fine
        latest_price_signal=latest_signal(chart),
        latest_rs_vs_market_signal=latest_signal(chart),
        ta_score=ta_score,
        above_bullish_support=is_above_bullish_support(chart),
    )


def _bars_with_tt_today(target_date: date) -> list[tuple[date, float, float]]:
    """Generate bars that produce a triple_top firing on target_date."""
    # 5 bars culminating in a TT. The TT fires on the last bar.
    return [
        (target_date - timedelta(days=4), 55.0, 50.0),
        (target_date - timedelta(days=3), 55.0, 51.0),
        (target_date - timedelta(days=2), 55.0, 51.0),
        (target_date - timedelta(days=1), 55.0, 51.0),
        (target_date, 56.0, 51.0),  # TT fires
    ]


class TestRunChecklist:
    def test_empty_universe_returns_empty_lists(self) -> None:
        result = run_checklist(
            stocks=[],
            raw_ohlc_by_symbol={},
            benchmark_ohlc=None,
            sector_indicators={},
            intra_sector_ranks={},
            yesterday_ta_scores={},
            as_of_date=date(2026, 5, 27),
        )
        assert result.list_1_fired_today == ()
        assert result.list_2_one_box_away == ()

    def test_stock_with_fresh_tt_lands_in_list_1(self) -> None:
        today = date(2026, 1, 9)
        state = _state("WIN", "Tech", _bars_with_tt_today(today), ta_score=4)
        result = run_checklist(
            stocks=[state],
            raw_ohlc_by_symbol={"WIN": _ohlc(_bars_with_tt_today(today))},
            benchmark_ohlc=None,
            sector_indicators=classify_all_sectors([state]),
            intra_sector_ranks=rank_within_sectors([state]),
            yesterday_ta_scores={"WIN": 3},  # TA went 3 -> 4
            as_of_date=today,
        )
        assert len(result.list_1_fired_today) == 1
        cand = result.list_1_fired_today[0]
        assert cand.symbol == "WIN"
        assert "triple_top" in cand.triggering_patterns
        assert cand.rank == 1

    def test_obos_above_115_eliminates(self) -> None:
        """Stock with extreme overbought OHLC should be eliminated, not ranked."""
        today = date(2026, 1, 9)
        state = _state("HOT", "Tech", _bars_with_tt_today(today))
        # Build OHLC that pushes OBOS above 115%: 50 flat days at 100, then spike to 200
        flat_dates = [date(2026, 1, 1) - timedelta(days=i) for i in range(60, 0, -1)]
        spike_ohlc = pd.DataFrame(
            [{"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 0}] * 59
            + [{"open": 200.0, "high": 200.0, "low": 200.0, "close": 200.0, "volume": 0}],
            index=flat_dates,
        )
        result = run_checklist(
            stocks=[state],
            raw_ohlc_by_symbol={"HOT": spike_ohlc},
            benchmark_ohlc=None,
            sector_indicators=classify_all_sectors([state]),
            intra_sector_ranks=rank_within_sectors([state]),
            yesterday_ta_scores={},
            as_of_date=today,
        )
        assert result.eliminated_obos_count == 1
        assert len(result.list_1_fired_today) == 0

    def test_ta_up_adds_w3_weight(self) -> None:
        """A stock whose TA went up should outrank an otherwise-identical one
        whose TA stayed flat."""
        today = date(2026, 1, 9)
        same_bars = _bars_with_tt_today(today)
        up = _state("UP", "Tech", same_bars, ta_score=4)
        flat = _state("FLAT", "Tech", same_bars, ta_score=4)
        result = run_checklist(
            stocks=[up, flat],
            raw_ohlc_by_symbol={"UP": _ohlc(same_bars), "FLAT": _ohlc(same_bars)},
            benchmark_ohlc=None,
            sector_indicators=classify_all_sectors([up, flat]),
            intra_sector_ranks=rank_within_sectors([up, flat]),
            yesterday_ta_scores={"UP": 3, "FLAT": 4},  # UP rose; FLAT didn't
            as_of_date=today,
        )
        assert len(result.list_1_fired_today) == 2
        assert result.list_1_fired_today[0].symbol == "UP"
        assert result.list_1_fired_today[1].symbol == "FLAT"
        assert result.list_1_fired_today[0].weights.w3 > Decimal("0")
        assert result.list_1_fired_today[1].weights.w3 == Decimal("0")

    def test_double_top_alone_does_not_qualify(self) -> None:
        """A stock firing only double_top (excluded from qualifying set) shouldn't
        appear in either list."""
        today = date(2026, 1, 7)
        bars = [
            (date(2026, 1, 5), 55.0, 50.0),
            (date(2026, 1, 6), 55.0, 51.0),
            (date(2026, 1, 7), 56.0, 51.0),  # DT only, no TT (only 1 prior X col)
        ]
        state = _state("DT", "Tech", bars)
        result = run_checklist(
            stocks=[state],
            raw_ohlc_by_symbol={"DT": _ohlc(bars)},
            benchmark_ohlc=None,
            sector_indicators=classify_all_sectors([state]),
            intra_sector_ranks=rank_within_sectors([state]),
            yesterday_ta_scores={},
            as_of_date=today,
        )
        assert len(result.list_1_fired_today) == 0

    def test_top_n_truncates(self) -> None:
        """If more candidates than top_n, only top_n are kept."""
        today = date(2026, 1, 9)
        # Create 5 candidates all with same TT pattern
        states = [_state(f"S{i}", "Tech", _bars_with_tt_today(today)) for i in range(5)]
        raw_ohlc = {s.symbol: _ohlc(_bars_with_tt_today(today)) for s in states}
        result = run_checklist(
            stocks=states,
            raw_ohlc_by_symbol=raw_ohlc,
            benchmark_ohlc=None,
            sector_indicators=classify_all_sectors(states),
            intra_sector_ranks=rank_within_sectors(states),
            yesterday_ta_scores={},
            as_of_date=today,
            top_n=3,
        )
        assert len(result.list_1_fired_today) == 3
        # Ranks should be 1, 2, 3
        assert [c.rank for c in result.list_1_fired_today] == [1, 2, 3]


class TestWeightsConfig:
    def test_default_w3_is_heavy(self) -> None:
        """W3 (TA up 24h) should be the largest weight per spec."""
        cfg = WeightsConfig()
        assert cfg.w3_ta_up_24h >= cfg.w1_one_box_rs_market
        assert cfg.w3_ta_up_24h >= cfg.w4_favored_sector


class TestWeightDescriptions:
    def test_descriptions_included_for_active_weights(self) -> None:
        today = date(2026, 1, 9)
        state = _state("WIN", "Tech", _bars_with_tt_today(today), ta_score=4)
        result = run_checklist(
            stocks=[state],
            raw_ohlc_by_symbol={"WIN": _ohlc(_bars_with_tt_today(today))},
            benchmark_ohlc=None,
            sector_indicators=classify_all_sectors([state]),
            intra_sector_ranks=rank_within_sectors([state]),
            yesterday_ta_scores={"WIN": 3},
            as_of_date=today,
        )
        cand = result.list_1_fired_today[0]
        # At minimum, the TA-up description should be present
        assert any("TA score rose" in d for d in cand.weight_descriptions)
