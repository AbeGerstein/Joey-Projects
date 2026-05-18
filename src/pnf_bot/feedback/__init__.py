"""Phase 6 — feedback loop.

Tracks every live recommendation the bot makes and measures its forward
performance. Surfaces a weekly/monthly scoreboard that compares live
results to the backtest expectations, enabling continuous calibration.

Public API:
    from pnf_bot.feedback import (
        record_recommendation,
        update_forward_returns,
        compute_scoreboard,
    )
"""

from pnf_bot.feedback.tracker import (
    LiveRecommendation,
    Scoreboard,
    compute_scoreboard,
    record_recommendation,
    update_forward_returns,
)

__all__ = [
    "LiveRecommendation",
    "Scoreboard",
    "compute_scoreboard",
    "record_recommendation",
    "update_forward_returns",
]
