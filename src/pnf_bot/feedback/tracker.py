"""Recommendation tracker — records every surfaced name and its forward returns.

Workflow:
1. On each daily run, after the report is generated, call
   `record_recommendation()` for every candidate in Section A and B.
2. Periodically (e.g., weekly), call `update_forward_returns()` to fill
   in the 1m/3m/6m/12m returns for past recommendations now that enough
   time has passed.
3. Call `compute_scoreboard()` to produce a summary of live performance
   over a date range.

This data is the basis for ongoing tuning — if live performance diverges
from the backtest, that's a signal to re-run weight tuning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from pnf_bot.data import storage
from pnf_bot.scoring.composite import ScoredCandidate


@dataclass(frozen=True)
class LiveRecommendation:
    """A live recommendation record with its forward returns (if available)."""

    recommended_at: date
    symbol: str
    section: str
    primary_pattern: str | None
    final_score: float
    fired_last_night: bool
    entry_price: Decimal | None
    return_1m: float | None
    return_3m: float | None
    return_6m: float | None
    return_12m: float | None


@dataclass(frozen=True)
class HorizonScore:
    """One horizon's live-performance metrics."""

    horizon_label: str
    n_picks: int
    hit_rate: float
    avg_winner: float
    avg_loser: float
    avg_return: float


@dataclass(frozen=True)
class Scoreboard:
    """Aggregate live-performance summary over a date range."""

    start_date: date
    end_date: date
    section: str  # "pre_momentum", "in_momentum", or "all"
    total_recommendations: int
    horizons: tuple[HorizonScore, ...]


def record_recommendation(
    db_path: Path | str,
    recommended_at: date,
    candidate: ScoredCandidate,
    entry_price: Decimal | None = None,
) -> int:
    """Persist one candidate as a live recommendation. Returns the new row id.

    Idempotent on (recommended_at, symbol, section) — re-running for the same
    date and stock skips the insert silently.
    """
    primary = candidate.matched_patterns[0].pattern_type if candidate.matched_patterns else None
    with storage.get_session(db_path) as session:
        existing = session.execute(
            select(storage.LiveRecommendationRow).where(
                storage.LiveRecommendationRow.recommended_at == recommended_at,
                storage.LiveRecommendationRow.symbol == candidate.symbol,
                storage.LiveRecommendationRow.section == candidate.section,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing.id
        row = storage.LiveRecommendationRow(
            recommended_at=recommended_at,
            symbol=candidate.symbol,
            section=candidate.section,
            primary_pattern=primary,
            final_score=Decimal(str(candidate.final_score)),
            fired_last_night=candidate.fired_last_night,
            entry_price=entry_price,
        )
        session.add(row)
        session.commit()
        return row.id


def update_forward_returns(
    db_path: Path | str,
    universe_ohlc: dict[str, pd.DataFrame],
) -> int:
    """Fill in 1m/3m/6m/12m returns for past recommendations.

    Iterates over LiveRecommendationRow records that have unfilled forward
    returns and enough time has passed since the recommendation date. For
    each unfilled cell, looks up the forward return from universe_ohlc.

    Returns the count of cells updated.
    """
    cells_updated = 0
    horizons = {21: "return_1m", 63: "return_3m", 126: "return_6m", 252: "return_12m"}

    with storage.get_session(db_path) as session:
        rows = session.execute(select(storage.LiveRecommendationRow)).scalars().all()
        for row in rows:
            ohlc = universe_ohlc.get(row.symbol)
            if ohlc is None:
                continue
            for horizon_days, column_name in horizons.items():
                if getattr(row, column_name) is not None:
                    continue
                ret = _compute_forward_return(ohlc, row.recommended_at, horizon_days)
                if ret is not None:
                    setattr(row, column_name, Decimal(str(round(ret, 6))))
                    cells_updated += 1
        session.commit()
    return cells_updated


def compute_scoreboard(
    db_path: Path | str,
    start_date: date,
    end_date: date,
    section: str = "all",  # "pre_momentum", "in_momentum", or "all"
) -> Scoreboard:
    """Aggregate live-performance metrics over a date range.

    Per-horizon hit rate, avg winner, avg loser, avg return.
    """
    horizons_def = [
        ("1m", "return_1m"),
        ("3m", "return_3m"),
        ("6m", "return_6m"),
        ("12m", "return_12m"),
    ]
    with storage.get_session(db_path) as session:
        query = select(storage.LiveRecommendationRow).where(
            storage.LiveRecommendationRow.recommended_at >= start_date,
            storage.LiveRecommendationRow.recommended_at <= end_date,
        )
        if section != "all":
            query = query.where(storage.LiveRecommendationRow.section == section)
        rows = session.execute(query).scalars().all()

    total = len(rows)
    horizons: list[HorizonScore] = []
    for label, col in horizons_def:
        returns = [float(getattr(r, col)) for r in rows if getattr(r, col) is not None]
        if not returns:
            horizons.append(
                HorizonScore(
                    horizon_label=label, n_picks=0, hit_rate=0.0,
                    avg_winner=0.0, avg_loser=0.0, avg_return=0.0,
                )
            )
            continue
        winners = [r for r in returns if r > 0]
        losers = [r for r in returns if r <= 0]
        horizons.append(
            HorizonScore(
                horizon_label=label,
                n_picks=len(returns),
                hit_rate=len(winners) / len(returns),
                avg_winner=sum(winners) / len(winners) if winners else 0.0,
                avg_loser=sum(losers) / len(losers) if losers else 0.0,
                avg_return=sum(returns) / len(returns),
            )
        )
    return Scoreboard(
        start_date=start_date,
        end_date=end_date,
        section=section,
        total_recommendations=total,
        horizons=tuple(horizons),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_forward_return(
    ohlc: pd.DataFrame, entry_date: date, horizon_trading_days: int
) -> float | None:
    if "close" not in ohlc.columns:
        return None
    df = ohlc.sort_index()
    candidate_dates = [idx.date() if hasattr(idx, "date") else idx for idx in df.index]
    try:
        entry_idx = candidate_dates.index(entry_date)
    except ValueError:
        return None
    exit_idx = entry_idx + horizon_trading_days
    if exit_idx >= len(df):
        return None
    entry_price = float(df.iloc[entry_idx]["close"])
    exit_price = float(df.iloc[exit_idx]["close"])
    if entry_price <= 0:
        return None
    return (exit_price - entry_price) / entry_price
