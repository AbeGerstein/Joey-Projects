"""Tests for the Weekly OBOS% indicator."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

from pnf_bot.scoring.obos import (
    compute_obos,
    is_above_hard_overbought,
    obos_weight,
)


def _flat_closes(n: int, price: float) -> pd.DataFrame:
    """Build an OHLC frame with `n` bars all at the same close price."""
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(n)]
    return pd.DataFrame(
        {"open": price, "high": price, "low": price, "close": price, "volume": 0},
        index=dates,
    )


def _trending_closes(n: int, start: float, slope: float) -> pd.DataFrame:
    """Build an OHLC frame with a linear price ramp from `start`, slope per day."""
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(n)]
    closes = [start + slope * i for i in range(n)]
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 0},
        index=dates,
    )


class TestComputeObos:
    def test_flat_history_returns_zero(self) -> None:
        """A perfectly flat price series has zero std → OBOS = 0."""
        ohlc = _flat_closes(60, 100.0)
        assert compute_obos(ohlc) == Decimal("0")

    def test_insufficient_history_returns_none(self) -> None:
        ohlc = _flat_closes(20, 100.0)
        assert compute_obos(ohlc) is None

    def test_price_above_ma_is_positive(self) -> None:
        """A trending-up series should have positive OBOS at the latest bar."""
        ohlc = _trending_closes(60, start=100.0, slope=0.5)
        obos = compute_obos(ohlc)
        assert obos is not None
        assert obos > Decimal("0")

    def test_price_below_ma_is_negative(self) -> None:
        """A trending-down series should have negative OBOS."""
        ohlc = _trending_closes(60, start=100.0, slope=-0.5)
        obos = compute_obos(ohlc)
        assert obos is not None
        assert obos < Decimal("0")

    def test_empty_input_returns_none(self) -> None:
        assert compute_obos(pd.DataFrame()) is None


class TestHardOverbought:
    def test_above_threshold_eliminates(self) -> None:
        assert is_above_hard_overbought(Decimal("120")) is True

    def test_below_threshold_keeps(self) -> None:
        assert is_above_hard_overbought(Decimal("100")) is False

    def test_at_threshold_keeps(self) -> None:
        """115 exactly should NOT eliminate (must be strictly above)."""
        assert is_above_hard_overbought(Decimal("115")) is False

    def test_none_keeps(self) -> None:
        """Missing OBOS data should not eliminate the stock."""
        assert is_above_hard_overbought(None) is False


class TestObosWeight:
    def test_max_at_or_below_minus_100(self) -> None:
        """Deeply oversold → full weight."""
        assert obos_weight(Decimal("-100")) == Decimal("1.0")
        assert obos_weight(Decimal("-150")) == Decimal("1.0")

    def test_zero_at_hard_cut(self) -> None:
        """At +115% the weight should be 0."""
        assert obos_weight(Decimal("115")) == Decimal("0")

    def test_zero_above_hard_cut(self) -> None:
        assert obos_weight(Decimal("200")) == Decimal("0")

    def test_neutral_at_zero(self) -> None:
        """OBOS = 0 (at the MA) → ~middle of the weight range."""
        w = obos_weight(Decimal("0"))
        # span is 215, distance from cut is 115, so weight = 115/215 ≈ 0.535
        assert Decimal("0.5") < w < Decimal("0.6")

    def test_none_gives_neutral(self) -> None:
        """Missing data → 50% of max weight (neither penalized nor boosted)."""
        assert obos_weight(None) == Decimal("0.5")

    def test_monotonic_decreasing_in_obos(self) -> None:
        """As OBOS rises, weight should decrease (less attractive)."""
        a = obos_weight(Decimal("-50"))
        b = obos_weight(Decimal("0"))
        c = obos_weight(Decimal("50"))
        d = obos_weight(Decimal("100"))
        assert a > b > c > d
