"""Tests for the Norgate adapter layer that don't require a live SDK or NDU."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from pnf_bot.data import norgate


class _FakeAdjustment:
    TOTALRETURN = "TOTALRETURN"
    CAPITAL = "CAPITAL"
    NONE = "NONE"


class _FakePadding:
    NONE = "PAD_NONE"


class _FakeSDK:
    """Stub norgatedata module exposing only what fetch_ohlc touches."""

    StockPriceAdjustmentType = _FakeAdjustment
    PaddingType = _FakePadding

    def __init__(self) -> None:
        self.last_call_kwargs: dict | None = None

    def price_timeseries(self, symbol: str, **kwargs):  # noqa: ANN003, ANN201
        self.last_call_kwargs = {"symbol": symbol, **kwargs}
        return pd.DataFrame()


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch) -> _FakeSDK:
    sdk = _FakeSDK()
    monkeypatch.setattr(norgate, "_require_sdk", lambda: sdk)
    return sdk


def test_fetch_ohlc_defaults_to_wide_range_when_both_dates_none(fake_sdk: _FakeSDK) -> None:
    """Regression: Norgate's SDK returns 0 rows when start_date and end_date are both None.

    The bot's daily-run calls fetch_ohlc with no dates expecting "all history",
    so fetch_ohlc must translate that into a real date range before delegating.
    """
    norgate.fetch_ohlc("AAPL")

    assert fake_sdk.last_call_kwargs is not None
    call = fake_sdk.last_call_kwargs
    assert call["start_date"] is not None, "fetch_ohlc must not pass start_date=None to SDK"
    assert call["end_date"] is not None, "fetch_ohlc must not pass end_date=None to SDK"
    # Window must cover enough history for P&F analysis (10+ years).
    span_days = (call["end_date"] - call["start_date"]).days
    assert span_days >= 365 * 10, f"default window {span_days} days is too narrow"
    # End date should be no later than today.
    assert call["end_date"] <= date.today()


def test_fetch_ohlc_passes_explicit_dates_through(fake_sdk: _FakeSDK) -> None:
    """Caller-supplied dates must reach the SDK unchanged."""
    start = date(2020, 1, 1)
    end = date(2024, 6, 30)
    norgate.fetch_ohlc("AAPL", start_date=start, end_date=end)

    assert fake_sdk.last_call_kwargs is not None
    assert fake_sdk.last_call_kwargs["start_date"] == start
    assert fake_sdk.last_call_kwargs["end_date"] == end


def test_fetch_ohlc_preserves_partial_dates(fake_sdk: _FakeSDK) -> None:
    """If only one of start/end is None, don't trigger the both-None defaulting."""
    end = date(2025, 1, 1)
    norgate.fetch_ohlc("AAPL", end_date=end)

    assert fake_sdk.last_call_kwargs is not None
    # start_date may be None (or whatever caller passed); we only defaulted when BOTH were None.
    assert fake_sdk.last_call_kwargs["end_date"] == end
    assert fake_sdk.last_call_kwargs["start_date"] is None


def test_fetch_ohlc_normalizes_norgate_column_names(fake_sdk: _FakeSDK, monkeypatch: pytest.MonkeyPatch) -> None:
    """Norgate returns capitalized column names; fetch_ohlc must lowercase them."""
    sample = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [100]},
        index=pd.to_datetime([date.today() - timedelta(days=1)]),
    )

    def fake_call(symbol: str, **kwargs):  # noqa: ANN003, ANN201
        fake_sdk.last_call_kwargs = {"symbol": symbol, **kwargs}
        return sample

    monkeypatch.setattr(fake_sdk, "price_timeseries", fake_call)
    df = norgate.fetch_ohlc("AAPL", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
    assert set(df.columns) >= {"open", "high", "low", "close", "volume"}
