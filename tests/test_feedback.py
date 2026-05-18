"""Tests for the live recommendation tracker and scoreboard."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from pnf_bot.data import storage
from pnf_bot.feedback import (
    compute_scoreboard,
    record_recommendation,
    update_forward_returns,
)
from pnf_bot.scoring.composite import ScoredCandidate


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "feedback.db"
    storage.init_database(db_path)
    return db_path


def _candidate(symbol: str, score: float, section: str = "pre_momentum") -> ScoredCandidate:
    return ScoredCandidate(
        symbol=symbol,
        section=section,
        base_score=score / 2,
        freshness_multiplier=2.0,
        final_score=score,
        matched_patterns=(),
        most_recent_pattern_date=date(2026, 1, 10),
        ta_equivalent_score=3,
        fired_last_night=True,
    )


class TestRecordRecommendation:
    def test_persists_one_recommendation(self, tmp_db: Path) -> None:
        cand = _candidate("AAPL", 0.85)
        row_id = record_recommendation(tmp_db, date(2026, 5, 18), cand)
        assert row_id > 0

    def test_idempotent_on_duplicate(self, tmp_db: Path) -> None:
        """Re-recording the same (date, symbol, section) returns same row id."""
        cand = _candidate("AAPL", 0.85)
        id1 = record_recommendation(tmp_db, date(2026, 5, 18), cand)
        id2 = record_recommendation(tmp_db, date(2026, 5, 18), cand)
        assert id1 == id2

    def test_different_sections_create_separate_rows(self, tmp_db: Path) -> None:
        pre = _candidate("AAPL", 0.85, section="pre_momentum")
        in_mom = _candidate("AAPL", 0.75, section="in_momentum")
        id1 = record_recommendation(tmp_db, date(2026, 5, 18), pre)
        id2 = record_recommendation(tmp_db, date(2026, 5, 18), in_mom)
        assert id1 != id2


class TestUpdateForwardReturns:
    def test_fills_in_returns_for_eligible_picks(self, tmp_db: Path) -> None:
        """A recommendation old enough to have 1m return gets its return_1m populated."""
        cand = _candidate("AAPL", 0.85)
        entry_date = date(2026, 1, 5)
        record_recommendation(tmp_db, entry_date, cand)

        # Build OHLC with 60 days of data — enough for 1m horizon
        ohlc = pd.DataFrame(
            {
                "close": [100.0 + i * 0.5 for i in range(60)],
                "open": [100.0 + i * 0.5 for i in range(60)],
                "high": [101.0 + i * 0.5 for i in range(60)],
                "low": [99.0 + i * 0.5 for i in range(60)],
                "volume": [1_000_000] * 60,
            },
            index=[entry_date + timedelta(days=i) for i in range(60)],
        )
        cells_updated = update_forward_returns(tmp_db, {"AAPL": ohlc})
        assert cells_updated > 0

        # Verify the 1m return is now populated
        with storage.get_session(tmp_db) as session:
            row = session.query(storage.LiveRecommendationRow).first()
            assert row.return_1m is not None


class TestScoreboard:
    def test_scoreboard_with_no_recommendations(self, tmp_db: Path) -> None:
        sb = compute_scoreboard(tmp_db, date(2026, 1, 1), date(2026, 12, 31))
        assert sb.total_recommendations == 0
        assert all(h.n_picks == 0 for h in sb.horizons)

    def test_scoreboard_filters_by_section(self, tmp_db: Path) -> None:
        record_recommendation(tmp_db, date(2026, 1, 10), _candidate("AAPL", 0.8, "pre_momentum"))
        record_recommendation(tmp_db, date(2026, 1, 10), _candidate("MSFT", 0.7, "in_momentum"))

        sb_pre = compute_scoreboard(
            tmp_db, date(2026, 1, 1), date(2026, 12, 31), section="pre_momentum"
        )
        assert sb_pre.total_recommendations == 1
        sb_all = compute_scoreboard(
            tmp_db, date(2026, 1, 1), date(2026, 12, 31), section="all"
        )
        assert sb_all.total_recommendations == 2
