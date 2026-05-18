"""Smoke tests for the storage layer.

Norgate-dependent tests are deferred until the subscription is active. These
tests exercise only schema creation and the persistence layer's own logic.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from pnf_bot.data import storage


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to a fresh temporary SQLite database with schema applied."""
    db_path = tmp_path / "test_pnf.db"
    storage.init_database(db_path)
    return db_path


def test_init_database_creates_schema(tmp_db: Path) -> None:
    """init_database should create the SQLite file and all tables."""
    assert tmp_db.exists()
    with storage.get_session(tmp_db) as session:
        # Empty tables exist and are queryable
        assert session.query(storage.Ticker).count() == 0
        assert session.query(storage.DailyBar).count() == 0
        assert session.query(storage.SignalState).count() == 0
        assert session.query(storage.ReportArchive).count() == 0


def test_init_database_is_idempotent(tmp_db: Path) -> None:
    """Calling init_database twice should not raise or destroy existing data."""
    with storage.get_session(tmp_db) as session:
        session.add(storage.Ticker(symbol="TEST", name="Test Inc.", is_active=True))
        session.commit()

    # Re-init — should be a no-op for existing tables
    storage.init_database(tmp_db)

    with storage.get_session(tmp_db) as session:
        assert session.query(storage.Ticker).count() == 1


def test_ticker_persistence(tmp_db: Path) -> None:
    """Tickers can be inserted, queried, and updated."""
    with storage.get_session(tmp_db) as session:
        session.add(
            storage.Ticker(
                symbol="AAPL",
                name="Apple Inc.",
                exchange="NASDAQ",
                sector="Information Technology",
                industry="Technology Hardware",
                is_active=True,
            )
        )
        session.commit()

    with storage.get_session(tmp_db) as session:
        aapl = session.get(storage.Ticker, "AAPL")
        assert aapl is not None
        assert aapl.name == "Apple Inc."
        assert aapl.sector == "Information Technology"
        assert aapl.is_active is True


def test_daily_bar_persistence(tmp_db: Path) -> None:
    """Daily bars can be persisted and queried by symbol+date."""
    with storage.get_session(tmp_db) as session:
        session.add(storage.Ticker(symbol="MSFT", name="Microsoft", is_active=True))
        session.add(
            storage.DailyBar(
                symbol="MSFT",
                trade_date=date(2026, 5, 18),
                open=Decimal("420.50"),
                high=Decimal("425.10"),
                low=Decimal("419.80"),
                close=Decimal("424.00"),
                volume=18_500_000,
            )
        )
        session.commit()

    with storage.get_session(tmp_db) as session:
        bar = session.get(storage.DailyBar, ("MSFT", date(2026, 5, 18)))
        assert bar is not None
        assert bar.close == Decimal("424.00")
        assert bar.volume == 18_500_000


def test_signal_state_unique_per_day(tmp_db: Path) -> None:
    """SignalState enforces one row per (symbol, evaluation_date)."""
    with storage.get_session(tmp_db) as session:
        session.add(storage.Ticker(symbol="NVDA", name="NVIDIA", is_active=True))
        session.add(
            storage.SignalState(
                symbol="NVDA",
                evaluation_date=date(2026, 5, 17),
                current_signal="double_top",
                current_signal_date=date(2026, 5, 15),
                is_on_buy_signal=True,
                classification="in_momentum",
            )
        )
        session.commit()

    with storage.get_session(tmp_db) as session:
        from sqlalchemy.exc import IntegrityError

        session.add(
            storage.SignalState(
                symbol="NVDA",
                evaluation_date=date(2026, 5, 17),
                current_signal="triple_top",  # different content
                is_on_buy_signal=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_report_archive_persistence(tmp_db: Path) -> None:
    """ReportArchive captures every report generated for the compliance audit trail."""
    with storage.get_session(tmp_db) as session:
        session.add(
            storage.ReportArchive(
                generated_at=datetime(2026, 5, 18, 7, 30),
                report_date=date(2026, 5, 18),
                recipient_email="Jromero816@yahoo.com",
                subject_line="Daily PnF stock report",
                pdf_path="reports/archive/2026-05-18.pdf",
                parameter_snapshot_json='{"section_a_top_n": 10}',
                candidate_count_section_a=10,
                candidate_count_section_b=10,
                candidate_count_new_last_night=3,
                delivery_status="sent",
            )
        )
        session.commit()

    with storage.get_session(tmp_db) as session:
        archive = session.query(storage.ReportArchive).first()
        assert archive is not None
        assert archive.recipient_email == "Jromero816@yahoo.com"
        assert archive.candidate_count_section_a == 10
