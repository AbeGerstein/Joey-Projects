"""Composite scoring — turns pattern detections into ranked daily candidates.

Three outputs per daily run:
1. **Section A — Pre-Momentum Candidates**: stocks at the start of a
   potential move. Ranked by composite pre-momentum score × freshness.
2. **Section B — In-Momentum Candidates**: stocks already in strong,
   sustainable momentum. Exhausted names are excluded.
3. **"New Patterns from Last Night" callout**: every stock where any
   pre-momentum pattern fired on the most recent trading day, regardless
   of overall score.

The composite-score weights mirror the methodology doc and are tunable
in Phase 4 backtest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pnf_bot.pnf.types import PnFChart
from pnf_bot.scoring.anti_patterns import is_exhausted
from pnf_bot.scoring.in_momentum import detect_in_momentum_patterns
from pnf_bot.scoring.pre_momentum import detect_pre_momentum_patterns
from pnf_bot.scoring.ta_composite import compute_ta_equivalent
from pnf_bot.scoring.types import PatternMatch

# ---------------------------------------------------------------------------
# Freshness multipliers — applied to the composite score based on how
# recently the pattern fired. See methodology doc Section 4.
# ---------------------------------------------------------------------------


def freshness_multiplier(pattern_date: date, as_of_date: date) -> float:
    """Return the multiplier applied to a pattern's score based on its age.

    1 trading day ago → 2.0
    2-3 days ago → 1.5
    4-10 days ago → 1.0 (baseline)
    11-30 days ago → 0.7
    > 30 days ago → 0.4
    """
    days_ago = (as_of_date - pattern_date).days
    if days_ago < 0:
        # Defensive: future-dated pattern (shouldn't happen, but handle)
        return 1.0
    if days_ago <= 1:
        return 2.0
    if days_ago <= 3:
        return 1.5
    if days_ago <= 10:
        return 1.0
    if days_ago <= 30:
        return 0.7
    return 0.4


# ---------------------------------------------------------------------------
# Composite score weights — initial best-guess. Tuned in Phase 4 backtest.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompositeWeights:
    """Tunable weights for combining the score components.

    Pre-momentum and in-momentum share the same shape but with different
    weight values per the methodology doc.
    """

    pattern_setup: float = 0.30
    rs_regime: float = 0.20
    sector_tailwind: float = 0.15
    trendline_distance: float = 0.15
    time_in_base: float = 0.10
    ta_score_modifier: float = 0.10  # Negative weight in pre-momentum, positive in in-momentum


PRE_MOMENTUM_DEFAULT_WEIGHTS = CompositeWeights()
IN_MOMENTUM_DEFAULT_WEIGHTS = CompositeWeights()


# ---------------------------------------------------------------------------
# Candidate record — what flows from scoring into the report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoredCandidate:
    """A stock ranked for inclusion in Section A or Section B.

    Includes the raw pattern matches, the composite score, the freshness
    multiplier applied, and the final ranking score. The report renders
    everything from this record.
    """

    symbol: str
    section: str  # "pre_momentum" or "in_momentum"
    base_score: float
    freshness_multiplier: float
    final_score: float
    matched_patterns: tuple[PatternMatch, ...]
    most_recent_pattern_date: date
    ta_equivalent_score: int
    fired_last_night: bool


# ---------------------------------------------------------------------------
# Per-stock scoring
# ---------------------------------------------------------------------------


def score_stock_pre_momentum(
    symbol: str,
    price_chart: PnFChart,
    rs_chart: PnFChart | None = None,
    sector_bpi_chart: PnFChart | None = None,
    sector_bpi_state: str | None = None,
    as_of_date: date | None = None,
    weights: CompositeWeights = PRE_MOMENTUM_DEFAULT_WEIGHTS,
) -> ScoredCandidate | None:
    """Compute the pre-momentum composite score for one stock.

    Returns None if no pre-momentum patterns match the chart — the stock
    is not a Section A candidate. Otherwise returns a ScoredCandidate
    with the final ranking score.

    A stock that is exhausted (per anti_patterns) is NOT a pre-momentum
    candidate by definition — pre-momentum patterns require pre-breakout
    state, and exhausted charts are post-breakout.
    """
    if as_of_date is None:
        as_of_date = date.today()

    matches = detect_pre_momentum_patterns(
        price_chart, rs_chart=rs_chart, sector_bpi_chart=sector_bpi_chart,
        as_of_date=as_of_date,
    )
    if not matches:
        return None

    # Exhausted stocks are explicitly not pre-momentum
    if is_exhausted(price_chart):
        return None

    ta = compute_ta_equivalent(price_chart, rs_chart=rs_chart, sector_bpi_state=sector_bpi_state)
    pattern_setup_score = sum(m.strength for m in matches) / len(matches)
    rs_regime_score = _rs_regime_score(ta)
    sector_score = _sector_score(sector_bpi_state)
    trendline_score = _trendline_score(price_chart, favor_close_to_support=True)
    base_score = (
        weights.pattern_setup * pattern_setup_score
        + weights.rs_regime * rs_regime_score
        + weights.sector_tailwind * sector_score
        + weights.trendline_distance * trendline_score
        - weights.ta_score_modifier * (ta.score / 5.0)  # NEGATIVE for pre-momentum
    )

    most_recent_date = max(m.detected_date for m in matches)
    fresh_mult = freshness_multiplier(most_recent_date, as_of_date)
    final = base_score * fresh_mult
    fired_last_night = (as_of_date - most_recent_date).days <= 1

    return ScoredCandidate(
        symbol=symbol,
        section="pre_momentum",
        base_score=base_score,
        freshness_multiplier=fresh_mult,
        final_score=final,
        matched_patterns=tuple(matches),
        most_recent_pattern_date=most_recent_date,
        ta_equivalent_score=ta.score,
        fired_last_night=fired_last_night,
    )


def score_stock_in_momentum(
    symbol: str,
    price_chart: PnFChart,
    rs_chart: PnFChart | None = None,
    sector_bpi_state: str | None = None,
    as_of_date: date | None = None,
    weights: CompositeWeights = IN_MOMENTUM_DEFAULT_WEIGHTS,
) -> ScoredCandidate | None:
    """Compute the in-momentum composite score for one stock.

    Returns None if the stock is exhausted OR if no in-momentum patterns
    match. In-momentum gives a POSITIVE weight to the TA score (unlike
    pre-momentum's negative weight) — high-TA stocks are exactly what
    Section B wants.
    """
    if as_of_date is None:
        as_of_date = date.today()

    if is_exhausted(price_chart):
        return None

    matches = detect_in_momentum_patterns(price_chart, rs_chart=rs_chart, as_of_date=as_of_date)
    if not matches:
        return None

    ta = compute_ta_equivalent(price_chart, rs_chart=rs_chart, sector_bpi_state=sector_bpi_state)
    pattern_setup_score = sum(m.strength for m in matches) / len(matches)
    rs_regime_score = _rs_regime_score(ta)
    sector_score = _sector_score(sector_bpi_state)
    trendline_score = _trendline_score(price_chart, favor_close_to_support=False)
    base_score = (
        weights.pattern_setup * pattern_setup_score
        + weights.rs_regime * rs_regime_score
        + weights.sector_tailwind * sector_score
        + weights.trendline_distance * trendline_score
        + weights.ta_score_modifier * (ta.score / 5.0)  # POSITIVE for in-momentum
    )

    most_recent_date = max(m.detected_date for m in matches)
    fresh_mult = freshness_multiplier(most_recent_date, as_of_date)
    final = base_score * fresh_mult
    fired_last_night = (as_of_date - most_recent_date).days <= 1

    return ScoredCandidate(
        symbol=symbol,
        section="in_momentum",
        base_score=base_score,
        freshness_multiplier=fresh_mult,
        final_score=final,
        matched_patterns=tuple(matches),
        most_recent_pattern_date=most_recent_date,
        ta_equivalent_score=ta.score,
        fired_last_night=fired_last_night,
    )


# ---------------------------------------------------------------------------
# Daily-run aggregator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyReport:
    """The structured output for a single day's screening run.

    What the report-renderer (Phase 5) consumes to produce the PDF.
    """

    as_of_date: date
    new_patterns_last_night: tuple[ScoredCandidate, ...]
    section_a_top_n: tuple[ScoredCandidate, ...]  # pre-momentum candidates
    section_b_top_n: tuple[ScoredCandidate, ...]  # in-momentum candidates


def build_daily_report(
    candidates: list[ScoredCandidate],
    as_of_date: date,
    section_a_top_n: int = 10,
    section_b_top_n: int = 10,
) -> DailyReport:
    """Assemble a DailyReport from a flat list of scored candidates.

    The list typically comes from running score_stock_pre_momentum and
    score_stock_in_momentum across the universe. The aggregator:
    - Sorts each section by final_score descending
    - Trims to top_n per section
    - Extracts the "new last night" set (every pre-momentum candidate
      whose most recent pattern fired in the last trading day)
    """
    pre = sorted(
        (c for c in candidates if c.section == "pre_momentum"),
        key=lambda c: c.final_score,
        reverse=True,
    )
    in_mom = sorted(
        (c for c in candidates if c.section == "in_momentum"),
        key=lambda c: c.final_score,
        reverse=True,
    )
    new_last_night = tuple(c for c in pre if c.fired_last_night)
    return DailyReport(
        as_of_date=as_of_date,
        new_patterns_last_night=new_last_night,
        section_a_top_n=tuple(pre[:section_a_top_n]),
        section_b_top_n=tuple(in_mom[:section_b_top_n]),
    )


# ---------------------------------------------------------------------------
# Internal scoring components
# ---------------------------------------------------------------------------


def _rs_regime_score(ta) -> float:  # noqa: ANN001
    """0.0-1.0: 0.5 base + 0.25 each for RS buy and RS positive trend."""
    score = 0.0
    if ta.on_rs_buy_signal:
        score += 0.5
    if ta.rs_positive_trend:
        score += 0.5
    return score


def _sector_score(sector_bpi_state: str | None) -> float:
    """0.0-1.0 based on the sector's BPI state."""
    if sector_bpi_state is None:
        return 0.0
    favorable = {"bull_confirmed": 1.0, "bull_alert": 0.9, "bull_correction": 0.5}
    unfavorable = {"bear_confirmed": 0.0, "bear_correction": 0.3, "bear_alert": 0.1}
    return favorable.get(sector_bpi_state, unfavorable.get(sector_bpi_state, 0.5))


def _trendline_score(chart: PnFChart, favor_close_to_support: bool) -> float:
    """Score based on distance from the bullish support trendline.

    For pre-momentum (favor_close_to_support=True): closer to support is
    better (less extension, more upside room). Score declines as we
    extend further above support.

    For in-momentum (favor_close_to_support=False): some distance is fine,
    but blow-off territory is bad. Score peaks in the 3-10 box range,
    declines as we extend further.
    """
    from pnf_bot.pnf.trendlines import boxes_above_bullish_support

    boxes = boxes_above_bullish_support(chart)
    if favor_close_to_support:
        if boxes <= 3:
            return 1.0
        if boxes <= 8:
            return 0.7
        if boxes <= 15:
            return 0.4
        return 0.1
    # in-momentum: prefer 3-10 box range
    if 3 <= boxes <= 10:
        return 1.0
    if 0 <= boxes <= 2:
        return 0.7  # very early after breakout
    if 11 <= boxes <= 15:
        return 0.5
    return 0.2
