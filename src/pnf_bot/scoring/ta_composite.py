"""Internal Technical-Attributes-equivalent composite score (0-5).

Mirrors the structure of DWA's proprietary 0-5 TA score using inputs we
compute ourselves. Per docs/research/norgate-data.md and the TA-gap
discussion in docs/research/ndw-data-link-alternatives.md, this is the
functionally-equivalent composite the bot uses for the Norgate-only path.

Five binary conditions that tally to 0-5:
1. On a P&F price-chart buy signal
2. Above the bullish support trendline on the price chart
3. RS chart on a buy signal
4. RS chart in a positive trend (above its own bullish support line)
5. In a favorable sector BPI state (Bull Confirmed or Bull Alert)

Unlike DWA's proprietary formula, this composite is fully transparent — the
caller can see which of the 5 conditions are satisfied. This is the input
that drives the in-momentum scoring and the anti-pattern routing.
"""

from __future__ import annotations

from dataclasses import dataclass

from pnf_bot.pnf.bpi import BpiState
from pnf_bot.pnf.rs import is_rs_positive_trend, rs_signal_status
from pnf_bot.pnf.signals import latest_signal
from pnf_bot.pnf.trendlines import is_above_bullish_support
from pnf_bot.pnf.types import PnFChart


@dataclass(frozen=True)
class TaComposite:
    """0-5 internal TA-equivalent score with per-condition breakdown.

    `score` is the count of satisfied conditions.
    Each boolean field reports whether that condition was met.
    """

    score: int
    on_price_buy_signal: bool
    above_bullish_support: bool
    on_rs_buy_signal: bool
    rs_positive_trend: bool
    favorable_sector_bpi: bool


FAVORABLE_BPI_STATES: frozenset[BpiState] = frozenset({"bull_confirmed", "bull_alert"})


def compute_ta_equivalent(
    price_chart: PnFChart,
    rs_chart: PnFChart | None = None,
    sector_bpi_state: BpiState | None = None,
) -> TaComposite:
    """Compute the 0-5 internal TA-equivalent score for one stock.

    Inputs that are None (e.g., no RS chart available) contribute 0 to the
    score. The composite still works with partial inputs.
    """
    sig = latest_signal(price_chart)
    on_price_buy = bool(sig and sig.is_bullish)
    above_support = is_above_bullish_support(price_chart)

    if rs_chart is not None:
        on_rs_buy = rs_signal_status(rs_chart) == "buy"
        rs_pos_trend = is_rs_positive_trend(rs_chart)
    else:
        on_rs_buy = False
        rs_pos_trend = False

    favorable_sector = sector_bpi_state in FAVORABLE_BPI_STATES if sector_bpi_state else False

    score = sum(
        [
            on_price_buy,
            above_support,
            on_rs_buy,
            rs_pos_trend,
            favorable_sector,
        ]
    )
    return TaComposite(
        score=score,
        on_price_buy_signal=on_price_buy,
        above_bullish_support=above_support,
        on_rs_buy_signal=on_rs_buy,
        rs_positive_trend=rs_pos_trend,
        favorable_sector_bpi=favorable_sector,
    )
