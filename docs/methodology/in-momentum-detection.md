# Methodology: In-Momentum Stock Detection (Report Section B)

This is the sister document to [pre-momentum-detection.md](pre-momentum-detection.md). While Section A of the daily report surfaces stocks at the *start* of a potential move, Section B surfaces stocks **already in strong momentum** — names the advisor might still want to buy into despite the move being underway. Per advisor direction (2026-05-16), these names are not excluded from the report; they are simply presented separately so the advisor can distinguish between "early entry" and "late entry" trade ideas.

This is a deliberate design choice. Two different entries serve two different trade theses:

- **Section A (pre-momentum):** "I think this stock is about to start moving — I'm taking a small position now and adding if the breakout fires."
- **Section B (in-momentum):** "This stock is already running and the momentum looks durable — I'm willing to chase, with a tighter stop."

The bot's job in Section B is the same as Section A in spirit: **curate**. Not every stock in motion belongs here — many are extended past the point where chasing is sensible. Section B applies its own pattern logic to identify the in-momentum stocks worth surfacing and to exclude the ones that have already exhausted their move.

---

## Patterns that indicate strong, sustainable momentum (Section B candidates)

### 1. Recent buy signal still close to the breakout level

A stock that gave a P&F buy signal within the last 1–3 columns and currently trades within a small distance (e.g., < 5 boxes) of the signal price. The breakout has fired but the move has not yet extended — the chart is confirming, not exhausted.

**Detection:** Most recent signal is a buy signal that occurred within the last K columns (default K=3). Current price is within N boxes (default N=5) of the signal level.

### 2. On a buy signal, on a positive trend, RS positive

The classic "5-for-5'er" or "X-out-of-Y" type of strong-posture stock. All of:
- Current P&F state: on a buy signal
- Above 45° bullish support line
- RS chart on a buy signal
- RS positive trend
- Sector BPI in Bull Confirmed or Bull Alert

When all of these align and the stock is *not* yet extended, it's a high-conviction in-momentum candidate. The Technical Attributes score (if NDWEQTA is in use) is the direct mechanization of this — TA = 4 or 5 with a non-extended chart is a Section B candidate.

### 3. Pole pattern — continuation after consolidation

The "pole" pattern in Dorsey's framework: a long X column up (the pole), a sharp pullback that retraces roughly half the pole, and resumption upward. The resumption signal is a strong continuation indicator — the stock has digested its initial advance and is starting the next leg.

**Detection:** Identify a long X column (e.g., ≥10 boxes) followed by a single O column retracing ~50%, followed by an X column that has just exceeded the prior X column high.

### 4. Breakout from a fresh bullish triangle (the resolution itself)

The pre-momentum methodology flagged the *coiling* bullish triangle as a Section A pattern (catch it before the breakout). When the breakout actually fires, the same stock is now a Section B candidate for a short window — the resolution has just happened and the move is just starting to play out.

**Detection:** This is a transition. A stock that was in Section A two days ago (coiling triangle near breakout) and now has fired its breakout is now in Section B for 3–5 trading days while the move develops.

### 5. Catapult confirmed

A bullish catapult fires when the double-top breakout after the pullback completes. The pre-momentum doc flagged the *setup* (in the pullback phase). The confirmed catapult is the in-momentum equivalent.

**Detection:** Triple top in the chart history, followed by an O column pullback, followed by a double top that has just fired. The catapult is now active.

### 6. RS strengthening on an already-positive chart

A stock that has been on a price-chart buy signal for a while, and whose RS chart has *just* given a new buy signal. RS is accelerating relative to price — institutional flows are intensifying.

---

## When a stock is too extended for Section B (excluded)

Even within "stocks in momentum," some names are past the point of being responsibly chaseable. These are excluded from Section B (they don't appear anywhere in the report):

### 1. Parabolic X column

A single X column extending more than 15–20 boxes without any reversal. The risk/reward is now unfavorable — the next reversal (whenever it comes) will be sharp and the stop is uncomfortably far below.

### 2. Extremely far above bullish support line

More than ~15 boxes above the 45° trendline. Mean-reversion risk dominates.

### 3. Blow-off characteristics

Trading more than 50% above a long-term moving-average analog (e.g., halfway between the highest X and lowest O over the last 24 months). This is the classic late-cycle blow-off phase — the move is closer to its end than its beginning.

### 4. Recent sell signal warning

A stock that recently broke its bullish support trendline or fired a sell signal — even if the broader posture still looks strong, momentum is wavering. Drop from Section B.

---

## Composite in-momentum score

The score combines pattern strength, freshness, and risk:

| Component | Weight (initial) | What it captures |
|---|---|---|
| Active pattern score | 0.30 | Which of the in-momentum patterns above are active |
| Posture quality | 0.25 | Combination of: on buy signal, above support, positive RS, favorable sector BPI |
| Recency of breakout | 0.15 | How recently the underlying move began — newer is better (less extended) |
| Risk distance | 0.20 | Distance to logical P&F stop (the box below current trendline) as % of price — closer stop = better |
| TA score | 0.10 | High TA score is a positive here, opposite of pre-momentum (still penalized if combined with extension via the exclusion rules above) |

Freshness applies here too, but with smaller multipliers — by definition, in-momentum stocks are not freshly-triggered:

| Pattern triggered (trading days ago) | Score multiplier |
|---|---|
| 1–3 | ×1.3 |
| 4–10 | ×1.0 (baseline) |
| 11–30 | ×0.8 |
| > 30 | ×0.5 |

---

## Cross-section dynamics — a stock can move between sections over time

A stock's classification changes as its chart evolves:

| Day → Day | Classification |
|---|---|
| Triangle coiling | **Section A** — pre-momentum candidate (approaching breakout) |
| Triangle just broke out | **Section B** — in-momentum, recent breakout |
| Stock has rallied 10+ boxes since the breakout | **Section B** — still in-momentum but score declining |
| Stock has rallied 20+ boxes (parabolic) | **Excluded** — past the point of sensible entry |
| Stock pulls back and starts another base | **Section A** again — new pre-momentum setup may form |

The bot does not memorize prior classifications. Each day's report is built fresh from the current chart state. Long-time advisors will recognize names cycling through these states — that's the point.

---

## Implementation notes

- Section B is implemented as a parallel pipeline alongside Section A in Phase 4 (see [00-project-outline.md](../00-project-outline.md)). Same data inputs, different pattern detectors, different scoring weights.
- The daily report renders both sections per [Phase 5 spec](../00-project-outline.md#phase-5--reporting--delivery).
- The advisor can configure how many candidates appear in each section (default suggestion: top 10 in Section A, top 10 in Section B).
- The exclusion rules above ensure Section B is curated — chasing late-stage moves is a known failure mode in trading, and the bot should not enable it.

---

## References

- Dorsey, *Point and Figure Charting* — chapters on signal continuation, pole patterns, and catapults.
- [methodology/pre-momentum-detection.md](pre-momentum-detection.md) — the sister methodology for Section A.
- [methodology/point-and-figure.md](point-and-figure.md), [relative-strength.md](relative-strength.md), [bullish-percent-index.md](bullish-percent-index.md) — the underlying technical primitives.
