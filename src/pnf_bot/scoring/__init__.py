"""Phase 4 — scoring layer.

Takes the P&F engine's chart outputs and produces ranked candidates
for the daily report:
- Pre-momentum pattern detectors (7 patterns from the methodology doc)
- In-momentum pattern detectors (6 patterns)
- Anti-pattern exclusions (parabolic, blow-off, extended)
- TA-equivalent internal composite (0-5)
- Composite scoring with freshness multipliers
- "New patterns from last night" detection

Public API:
    from pnf_bot.scoring import (
        PatternMatch, PreMomentumPatternType, InMomentumPatternType,
        detect_pre_momentum_patterns,
        detect_in_momentum_patterns,
        compute_ta_equivalent,
    )
"""

from pnf_bot.scoring.anti_patterns import (
    ExhaustionReason,
    evaluate_anti_patterns,
    is_exhausted,
)
from pnf_bot.scoring.in_momentum import (
    InMomentumPatternType,
    detect_in_momentum_patterns,
)
from pnf_bot.scoring.pre_momentum import (
    PreMomentumPatternType,
    detect_pre_momentum_patterns,
)
from pnf_bot.scoring.ta_composite import TaComposite, compute_ta_equivalent
from pnf_bot.scoring.types import PatternMatch

__all__ = [
    "ExhaustionReason",
    "InMomentumPatternType",
    "PatternMatch",
    "PreMomentumPatternType",
    "TaComposite",
    "compute_ta_equivalent",
    "detect_in_momentum_patterns",
    "detect_pre_momentum_patterns",
    "evaluate_anti_patterns",
    "is_exhausted",
]
