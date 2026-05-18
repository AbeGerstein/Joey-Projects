"""SQLite storage layer.

Persists the universe of tickers, daily OHLC bars, signal state history,
and an archive of every report the bot has generated (compliance audit trail).

Designed for SQLite for v1 — schema is portable to Postgres + TimescaleDB
if scale ever demands it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class Ticker(Base):
    """One row per security in the universe.

    `is_active` flips false when Norgate marks the security delisted. We keep
    the row for historical reference (compliance: "why was XYZ recommended on date D?").
    """

    __tablename__ = "tickers"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    exchange: Mapped[str | None] = mapped_column(String(20))
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    delisted_date: Mapped[date | None] = mapped_column(Date)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    bars: Mapped[list["DailyBar"]] = relationship(back_populates="ticker")
    signals: Mapped[list["SignalState"]] = relationship(back_populates="ticker")


class DailyBar(Base):
    """One row per (ticker, trading day).

    Norgate returns split + dividend adjusted prices by default. We store
    adjusted only — unadjusted prices are not needed for P&F analysis since
    the chart construction is scale-invariant under proportional adjustments.
    """

    __tablename__ = "daily_bars"

    symbol: Mapped[str] = mapped_column(
        String(20), ForeignKey("tickers.symbol"), primary_key=True
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    volume: Mapped[int] = mapped_column(BigInteger, default=0)

    ticker: Mapped[Ticker] = relationship(back_populates="bars")

    __table_args__ = (Index("ix_daily_bars_date", "trade_date"),)


class SignalState(Base):
    """Tracks each ticker's P&F state as of each evaluation date.

    A "signal state" snapshot is taken after each daily run. This lets us:
    - Answer "what did the bot see for AAPL on 2026-04-10?" months later (compliance)
    - Detect signal changes (the freshness multiplier needs "what changed since yesterday?")
    - Backtest by replaying historical signal states
    """

    __tablename__ = "signal_state"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("tickers.symbol"))
    evaluation_date: Mapped[date] = mapped_column(Date)

    # Current P&F state
    current_signal: Mapped[str | None] = mapped_column(String(40))  # e.g., "double_top"
    current_signal_date: Mapped[date | None] = mapped_column(Date)
    current_signal_level: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    is_on_buy_signal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_above_bullish_support: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relative Strength
    rs_signal: Mapped[str | None] = mapped_column(String(20))  # "buy" or "sell"
    rs_signal_date: Mapped[date | None] = mapped_column(Date)
    rs_rank: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))

    # Internal TA-equivalent score (0-5)
    ta_equivalent_score: Mapped[int | None] = mapped_column()

    # Section classification: "pre_momentum", "in_momentum", or null
    classification: Mapped[str | None] = mapped_column(String(20))

    ticker: Mapped[Ticker] = relationship(back_populates="signals")

    __table_args__ = (
        UniqueConstraint("symbol", "evaluation_date", name="uq_signal_state_symbol_date"),
        Index("ix_signal_state_date", "evaluation_date"),
    )


class ReportArchive(Base):
    """One row per report generated. Required for the audit trail.

    Stores the full report contents plus the parameter snapshot — every
    weight, every threshold, every config value — that produced it.
    """

    __tablename__ = "reports_archive"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255))
    subject_line: Mapped[str] = mapped_column(String(255))
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    html_path: Mapped[str | None] = mapped_column(String(500))
    parameter_snapshot_json: Mapped[str] = mapped_column(String)
    candidate_count_section_a: Mapped[int] = mapped_column(default=0)
    candidate_count_section_b: Mapped[int] = mapped_column(default=0)
    candidate_count_new_last_night: Mapped[int] = mapped_column(default=0)
    delivery_status: Mapped[str] = mapped_column(String(30), default="pending")
    delivery_attempted_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivery_error: Mapped[str | None] = mapped_column(String)


def init_database(db_path: Path | str) -> None:
    """Create the schema if it does not exist.

    Idempotent — safe to call repeatedly.
    """
    engine = create_engine(_sqlite_url(db_path))
    Base.metadata.create_all(engine)


def get_session(db_path: Path | str) -> Session:
    """Open a session against the configured database.

    Caller is responsible for closing or using as a context manager.
    """
    engine = create_engine(_sqlite_url(db_path))
    return Session(engine)


def _sqlite_url(db_path: Path | str) -> str:
    """Build a SQLite URL from a path, creating parent directories as needed."""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{p.resolve()}"
