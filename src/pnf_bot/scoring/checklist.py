"""The checklist ranker — central output of the rework.

Produces two ranked lists per daily run:

  List 1: stocks where one of the qualifying patterns FIRED on the most
          recent trading day. (Double_top excluded per spec.)

  List 2: stocks where the price chart is exactly ONE BOX from firing one
          of those patterns. (Double_top excluded.)

Each list is independently ranked by a weighted score combining six
filters. Only one filter is a hard elimination — OBOS > 115% overbought.
All other filters add weight without eliminating.

Per-stock breakdown is preserved in the output so the report can show
WHY a stock ranked where it did.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pandas as pd

from pnf_bot.pnf.signals import SignalType, detect_signals
from pnf_bot.scoring.intra_sector_rank import (
    IntraSectorRank,
    intra_sector_weight,
)
from pnf_bot.scoring.obos import (
    compute_obos,
    is_above_hard_overbought,
    obos_weight,
)
from pnf_bot.scoring.one_box_away import (
    fired_today,
    one_box_away,
    one_box_away_from_rs_buy,
)
from pnf_bot.scoring.rew_risk import compute_rs_rew_risk
from pnf_bot.scoring.rrisk import compute_rrisk
from pnf_bot.scoring.sector_indicators import (
    SectorIndicators,
    is_favored,
)
from pnf_bot.scoring.stock_state import StockState


@dataclass(frozen=True)
class WeightsConfig:
    """Maximum weight contribution per filter. Sum of all max values is the
    upper bound a stock can score. Tune per advisor preference."""

    w1_one_box_rs_market: Decimal = Decimal("0.20")
    w2_one_box_rs_sector: Decimal = Decimal("0.20")  # v1: not yet wired (zero contribution)
    w3_ta_up_24h: Decimal = Decimal("0.50")           # heavy, per spec
    w4_favored_sector: Decimal = Decimal("0.30")
    w5_intra_sector_rank: Decimal = Decimal("0.30")
    w6_obos: Decimal = Decimal("0.30")


@dataclass(frozen=True)
class WeightBreakdown:
    """Per-stock contribution from each of the 6 weights, plus the total.

    Each field is the *actual* contribution (after applying tiering /
    conditions), not the max possible. Sum of all 6 equals `total`.
    """

    w1: Decimal
    w2: Decimal
    w3: Decimal
    w4: Decimal
    w5: Decimal
    w6: Decimal
    total: Decimal

    @classmethod
    def from_parts(cls, w1: Decimal, w2: Decimal, w3: Decimal,
                   w4: Decimal, w5: Decimal, w6: Decimal) -> WeightBreakdown:
        return cls(
            w1=w1, w2=w2, w3=w3, w4=w4, w5=w5, w6=w6,
            total=w1 + w2 + w3 + w4 + w5 + w6,
        )


@dataclass(frozen=True)
class RankedCandidate:
    """One stock in either List 1 or List 2 with full ranking detail."""

    symbol: str
    list_id: int                  # 1 (fired today) or 2 (one box away)
    triggering_patterns: tuple[SignalType, ...]
    weights: WeightBreakdown
    rank: int = 0
    # Report-only fields (no weight contribution)
    obos: Decimal | None = None
    rrisk: Decimal | None = None
    rew_risk: Decimal | None = None
    # Context for commentary
    sector: str | None = None
    sector_classification: str = "unfavored"
    intra_sector_rank: int | None = None
    intra_sector_size: int | None = None
    ta_score: int = 0
    ta_score_yesterday: int | None = None
    # Explanation strings for the report
    weight_descriptions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ChecklistReport:
    """The structured output of one checklist run."""

    as_of_date: date
    list_1_fired_today: tuple[RankedCandidate, ...]
    list_2_one_box_away: tuple[RankedCandidate, ...]
    eliminated_obos_count: int  # how many stocks were hard-eliminated by OBOS


def run_checklist(
    stocks: Iterable[StockState],
    raw_ohlc_by_symbol: dict[str, pd.DataFrame],
    benchmark_ohlc: pd.DataFrame | None,
    sector_indicators: dict[str, SectorIndicators],
    intra_sector_ranks: dict[str, IntraSectorRank],
    yesterday_ta_scores: dict[str, int],
    as_of_date: date,
    top_n: int = 30,
    weights_config: WeightsConfig | None = None,
) -> ChecklistReport:
    """Build the two ranked lists per the checklist spec.

    Inputs are pre-computed by the caller (daily_run) so this function is
    pure aggregation + ranking, no I/O.

    Args:
        stocks: every active StockState in the universe.
        raw_ohlc_by_symbol: OHLC dataframes keyed by symbol — used to
            compute OBOS, Rrisk per stock.
        benchmark_ohlc: SPX (or RSP proxy) OHLC for Rrisk calculation.
            None to skip Rrisk.
        sector_indicators: per-sector classification (output of
            classify_all_sectors).
        intra_sector_ranks: per-stock rank within sector (output of
            rank_within_sectors).
        yesterday_ta_scores: TA scores from the prior trading day's run.
            Missing entries treated as "no change" → W3 contributes 0.
        as_of_date: the trading day this run represents.
        top_n: how many candidates to keep per list.
        weights_config: per-filter max weights (defaults provided).
    """
    cfg = weights_config or WeightsConfig()
    stocks_list = list(stocks)

    list_1: list[RankedCandidate] = []
    list_2: list[RankedCandidate] = []
    obos_eliminated = 0

    for state in stocks_list:
        # ----- pattern detection: List 1 / List 2 membership -----
        signals = detect_signals(state.price_chart)
        fired = fired_today(signals, as_of_date)
        one_box = one_box_away(state.price_chart)

        if not fired and not one_box:
            continue  # not a candidate for either list

        # ----- OBOS hard elimination -----
        ohlc = raw_ohlc_by_symbol.get(state.symbol)
        obos = compute_obos(ohlc) if ohlc is not None else None
        if is_above_hard_overbought(obos):
            obos_eliminated += 1
            continue

        # ----- supplemental fields -----
        rrisk = (
            compute_rrisk(ohlc, benchmark_ohlc)
            if ohlc is not None and benchmark_ohlc is not None
            else None
        )
        rew_risk = compute_rs_rew_risk(state.rs_chart_vs_market)

        # ----- weights -----
        w1 = (
            cfg.w1_one_box_rs_market
            if one_box_away_from_rs_buy(state.rs_chart_vs_market)
            else Decimal("0")
        )
        # W2 (vs sector) wired in a later phase — sector indices not built yet.
        w2 = Decimal("0")

        ta_yesterday = yesterday_ta_scores.get(state.symbol)
        w3 = (
            cfg.w3_ta_up_24h
            if ta_yesterday is not None and state.ta_score > ta_yesterday
            else Decimal("0")
        )

        sector_class = sector_indicators.get(state.sector or "Unclassified")
        w4 = cfg.w4_favored_sector if is_favored(sector_class) else Decimal("0")

        rank_info = intra_sector_ranks.get(state.symbol)
        w5 = intra_sector_weight(rank_info, max_weight=cfg.w5_intra_sector_rank)

        w6 = obos_weight(obos, max_weight=cfg.w6_obos)

        breakdown = WeightBreakdown.from_parts(w1, w2, w3, w4, w5, w6)
        descriptions = _build_descriptions(
            w1, w2, w3, w4, w5, w6,
            state, sector_class, rank_info,
            ta_yesterday, obos,
        )

        common_fields = {
            "symbol": state.symbol,
            "triggering_patterns": tuple(sorted(fired if fired else one_box)),
            "weights": breakdown,
            "obos": obos,
            "rrisk": rrisk,
            "rew_risk": rew_risk,
            "sector": state.sector,
            "sector_classification": sector_class.classification if sector_class else "unfavored",
            "intra_sector_rank": rank_info.rank_position if rank_info else None,
            "intra_sector_size": rank_info.sector_size if rank_info else None,
            "ta_score": state.ta_score,
            "ta_score_yesterday": ta_yesterday,
            "weight_descriptions": descriptions,
        }

        if fired:
            list_1.append(RankedCandidate(list_id=1, **common_fields))
        # If a stock both fired and is one-box-away (rare but possible across
        # different patterns), put it in List 1 only — fired-today wins.
        if one_box and not fired:
            list_2.append(RankedCandidate(list_id=2, **common_fields))

    # ----- rank + truncate -----
    list_1_ranked = _rank_and_take(list_1, top_n)
    list_2_ranked = _rank_and_take(list_2, top_n)

    return ChecklistReport(
        as_of_date=as_of_date,
        list_1_fired_today=list_1_ranked,
        list_2_one_box_away=list_2_ranked,
        eliminated_obos_count=obos_eliminated,
    )


def _rank_and_take(
    candidates: list[RankedCandidate],
    top_n: int,
) -> tuple[RankedCandidate, ...]:
    """Sort candidates by total weight descending, assign rank, take top N."""
    sorted_list = sorted(candidates, key=lambda c: c.weights.total, reverse=True)
    out: list[RankedCandidate] = []
    for idx, c in enumerate(sorted_list[:top_n], start=1):
        # Re-create the dataclass with rank populated
        out.append(
            RankedCandidate(
                symbol=c.symbol,
                list_id=c.list_id,
                triggering_patterns=c.triggering_patterns,
                weights=c.weights,
                rank=idx,
                obos=c.obos,
                rrisk=c.rrisk,
                rew_risk=c.rew_risk,
                sector=c.sector,
                sector_classification=c.sector_classification,
                intra_sector_rank=c.intra_sector_rank,
                intra_sector_size=c.intra_sector_size,
                ta_score=c.ta_score,
                ta_score_yesterday=c.ta_score_yesterday,
                weight_descriptions=c.weight_descriptions,
            )
        )
    return tuple(out)


def _build_descriptions(
    w1: Decimal, w2: Decimal, w3: Decimal, w4: Decimal, w5: Decimal, w6: Decimal,
    state: StockState,
    sector_class: SectorIndicators | None,
    rank_info: IntraSectorRank | None,
    ta_yesterday: int | None,
    obos: Decimal | None,
) -> tuple[str, ...]:
    """Build human-readable descriptions of the weight contributions for the report."""
    desc: list[str] = []
    if w1 > 0:
        desc.append(f"1 box from new RS-vs-market buy (+{w1})")
    if w2 > 0:
        desc.append(f"1 box from new RS-vs-sector buy (+{w2})")
    if w3 > 0:
        desc.append(f"TA score rose {ta_yesterday}→{state.ta_score} (+{w3})")
    if w4 > 0 and sector_class is not None:
        desc.append(
            f"sector {state.sector} is FAVORED ({sector_class.positive_count}/4 indicators positive) (+{w4})"
        )
    if w5 > 0 and rank_info is not None:
        desc.append(
            f"ranked #{rank_info.rank_position} of {rank_info.sector_size} in sector ({rank_info.percentile:.0%}ile) (+{w5})"
        )
    if w6 > 0:
        obos_str = f"{obos}%" if obos is not None else "n/a"
        desc.append(f"OBOS {obos_str} (+{w6})")
    return tuple(desc)
