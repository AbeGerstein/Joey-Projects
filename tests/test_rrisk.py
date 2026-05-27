"""Tests for Rrisk (relative risk vs. SPX)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

from pnf_bot.scoring.rrisk import compute_rrisk


def _ohlc_from_closes(closes: list[float]) -> pd.DataFrame:
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(len(closes))]
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 0},
        index=dates,
    )


class TestComputeRrisk:
    def test_identical_series_returns_one(self) -> None:
        """A stock with the same daily returns as SPX has Rrisk = 1."""
        rng = np.random.default_rng(seed=42)
        spx_closes = (100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, 300)))).tolist()
        spx = _ohlc_from_closes(spx_closes)
        stock = _ohlc_from_closes(spx_closes)  # identical
        rrisk = compute_rrisk(stock, spx)
        assert rrisk == Decimal("1.000")

    def test_higher_vol_stock_gives_rrisk_above_one(self) -> None:
        """A stock with 2× SPX daily vol should have Rrisk ≈ 2."""
        rng = np.random.default_rng(seed=7)
        n = 300
        spx_returns = rng.normal(0, 0.01, n)
        stock_returns = rng.normal(0, 0.02, n)
        spx_closes = (100.0 * np.exp(np.cumsum(spx_returns))).tolist()
        stock_closes = (100.0 * np.exp(np.cumsum(stock_returns))).tolist()
        rrisk = compute_rrisk(_ohlc_from_closes(stock_closes), _ohlc_from_closes(spx_closes))
        assert rrisk is not None
        # Tolerate sample-noise: should be in [1.7, 2.3]
        assert Decimal("1.7") < rrisk < Decimal("2.3"), f"got {rrisk}"

    def test_lower_vol_stock_gives_rrisk_below_one(self) -> None:
        rng = np.random.default_rng(seed=13)
        n = 300
        spx_returns = rng.normal(0, 0.01, n)
        stock_returns = rng.normal(0, 0.005, n)
        spx_closes = (100.0 * np.exp(np.cumsum(spx_returns))).tolist()
        stock_closes = (100.0 * np.exp(np.cumsum(stock_returns))).tolist()
        rrisk = compute_rrisk(_ohlc_from_closes(stock_closes), _ohlc_from_closes(spx_closes))
        assert rrisk is not None
        assert Decimal("0.3") < rrisk < Decimal("0.7"), f"got {rrisk}"

    def test_insufficient_history_returns_none(self) -> None:
        rrisk = compute_rrisk(_ohlc_from_closes([100.0] * 50), _ohlc_from_closes([100.0] * 50))
        assert rrisk is None

    def test_empty_input_returns_none(self) -> None:
        assert compute_rrisk(pd.DataFrame(), _ohlc_from_closes([100.0] * 300)) is None
        assert compute_rrisk(_ohlc_from_closes([100.0] * 300), pd.DataFrame()) is None
