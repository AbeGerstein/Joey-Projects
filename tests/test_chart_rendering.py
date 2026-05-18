"""Tests for P&F chart rendering."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from pnf_bot.pnf import construct_chart
from pnf_bot.report.charts import render_pnf_chart, render_rs_chart


def _bars(start: date, hl: list[tuple[float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"open": (h + l) / 2, "high": h, "low": l, "close": (h + l) / 2, "volume": 1_000_000}
            for (h, l) in hl
        ],
        index=[start + timedelta(days=i) for i in range(len(hl))],
    )


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class TestPnfChartRendering:
    def test_renders_png(self) -> None:
        """The renderer returns valid PNG bytes."""
        bars = [
            (50.0, 50.0),
            (50.0, 46.0),
            (51.0, 46.0),
            (51.0, 47.0),
            (52.0, 47.0),
        ]
        chart = construct_chart("AAPL", _bars(date(2026, 1, 5), bars))
        png = render_pnf_chart(chart)
        assert png.startswith(PNG_SIGNATURE)
        assert len(png) > 1000  # reasonable PNG size

    def test_empty_chart_still_renders(self) -> None:
        """A chart with one bar still produces a valid PNG."""
        bars = [(50.0, 50.0)]
        chart = construct_chart("EMPTY", _bars(date(2026, 1, 5), bars))
        png = render_pnf_chart(chart)
        assert png.startswith(PNG_SIGNATURE)

    def test_render_with_trendlines_disabled(self) -> None:
        bars = [
            (50.0, 50.0),
            (50.0, 46.0),
            (51.0, 46.0),
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        png = render_pnf_chart(chart, show_trendlines=False)
        assert png.startswith(PNG_SIGNATURE)

    def test_render_with_signals_disabled(self) -> None:
        bars = [
            (50.0, 50.0),
            (50.0, 46.0),
            (51.0, 46.0),
            (51.0, 47.0),
            (52.0, 47.0),
        ]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        png = render_pnf_chart(chart, show_signals=False)
        assert png.startswith(PNG_SIGNATURE)

    def test_custom_title(self) -> None:
        bars = [(50.0, 50.0), (50.0, 46.0)]
        chart = construct_chart("T", _bars(date(2026, 1, 5), bars))
        png = render_pnf_chart(chart, title="My Custom Title")
        assert png.startswith(PNG_SIGNATURE)


class TestRsChartRendering:
    def test_renders_png(self) -> None:
        bars = [(100.0, 100.0), (105.0, 100.0), (110.0, 105.0)]
        rs_chart = construct_chart("AAPL_RS", _bars(date(2026, 1, 5), bars))
        png = render_rs_chart(rs_chart)
        assert png.startswith(PNG_SIGNATURE)
