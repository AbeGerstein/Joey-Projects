# Methodology: Pre-Momentum Detection

The bot's predictive intent — locked in 2026-05-16 — is to identify stocks **before** they enter a period of upward momentum. Catching the inflection, not confirming it after the fact. This document captures the patterns that historically precede meaningful upward moves in the P&F framework, the patterns that indicate momentum is already underway (and therefore disqualify a name), and the scoring logic that combines them into a daily candidate ranking.

The distinction matters. A stock that broke out last week and rallied 15% may still look "strong" on every conventional measure, but its highest-expected-value window is behind it. The bot is built to ignore those names and surface the ones approaching that window from below.

This is also consistent with the advisor's view of what makes idea generation valuable: any service can tell you what's already moving; the edge is in seeing what's about to.

---

## Why pre-momentum is the right framing for this screener

Three reasons drive the choice:

1. **Risk/reward asymmetry.** A stock that has already moved 30% has limited remaining upside and full downside if the move reverses. A stock with a setup that *suggests* a move is about to start has the full move ahead. The expected value calculation favors early entries.

2. **The advisor's edge.** A skilled P&F practitioner's edge is precisely in pattern recognition — seeing what is about to happen. Most automated screeners (including DWA's own Technical Attributes ranking) rank stocks already on buy signals with strong relative strength — i.e., stocks already in motion. The bot exists to apply the *anticipatory* lens systematically across the full US equity universe, which is what the advisor cannot do manually.

3. **Consistency with how DWA-style P&F is taught.** Dorsey's book repeatedly emphasizes *catching the move early* — entries near long-term support, after long bases, on initial buy signals after extended sell regimes. The "high TA score, big mover" stocks DWA's platform highlights are a useful confirmation tool but not the primary edge for someone using the methodology actively.

---

## Patterns that historically precede momentum (UPWEIGHT)

These are the patterns the bot looks for. Each one is described below with its detection logic and why it matters as a pre-momentum signal.

### 1. Bullish triangle near breakout

A coiling pattern of progressively lower highs and progressively higher lows, forming a triangle on the P&F chart. As the pattern tightens, supply and demand are coming into balance; the eventual resolution is often violent because the energy has been accumulating.

**Detection:** the most recent N (typically 3) columns form a converging pattern, and current price is within 1–2 boxes of the upper triangle boundary.

**Why it's pre-momentum:** the breakout from a triangle is the start of a move, not the middle. Catching the chart in the tightening phase puts the entry near the breakout level.

### 2. Long tail down reversal followed by initial buy signal

A capitulation O column — typically 17+ boxes (Dorsey's working definition of a "long tail") — followed by an X column that gives a buy signal by exceeding the prior X column high. The long tail itself marks the bottom; the subsequent buy signal is the entry.

**Detection:** find an O column ≥ 17 boxes within the last N columns, followed by an X column that has just produced a double top.

**Why it's pre-momentum:** long-tail reversals often precede multi-year regime changes from accumulating selling to sustained buying. The initial buy signal after the capitulation is the highest-conviction entry of the entire bottoming process.

### 3. First buy signal after an extended sell-signal regime

A stock has been on a P&F sell signal for an extended period (months to years). It suddenly gives its first buy signal. This is a regime change.

**Detection:** the current P&F state is "on a buy signal," and the immediately prior signal was a sell signal that persisted for at least M months (default M=6).

**Why it's pre-momentum:** prolonged weakness eventually exhausts sellers; the first buy signal after that exhaustion is statistically among the most reliable in the P&F framework. It's often the start of a multi-year recovery move.

### 4. Bullish catapult setup forming (not yet fired)

A bullish catapult is a triple top, followed by a pullback (one O column), followed by a double top breakout. The *setup* is in the pullback phase — after the triple top but before the second breakout fires.

**Detection:** the most recent prior signal was a triple top, the current column is an O column (the pullback), and the bottom of the current O column is above prior support.

**Why it's pre-momentum:** catching the chart in the pullback gives a position near the breakout level. When the double top fires (typically 1–3 boxes higher), the catapult is confirmed and the run begins. This is the canonical "pre-breakout" setup in Dorsey's framework.

### 5. Long-term Relative Strength turning positive

A stock's long-term RS chart (price / SPXEWI, plotted with 6.5% boxes) has been on an RS sell signal for an extended period. The RS chart just fired its first RS buy signal — regime change on relative performance.

**Detection:** RS chart most recent prior signal was a sell, persisting for ≥ M months. Current RS chart state is a buy signal.

**Why it's pre-momentum:** RS regime changes often precede price-chart regime changes by weeks to months. A stock that has just turned positive on long-term RS is becoming a leader before the price chart fully reflects it.

### 6. Sector BPI inflection from below 30%

The Bullish Percent Index for a sector has been below 30% (oversold regime) and has just reversed up into a column of X's — a "Bull Alert" state in Dorsey's six-state framework.

**Detection:** sector BPI series shows the current column is X's, the column immediately prior was O's, and the column low of the prior O column was below 30%.

**Why it's pre-momentum:** the strongest moves in a sector typically come *after* the sector BPI bottoms, when capital begins rotating back into beaten-down names. The leading stocks in a sector that's just had a BPI Bull Alert are at the start of a sector-wide move.

### 7. Sideways base with rising RS underneath

The price chart is in a sideways range (no clear trend, recent signals are mixed or neutral). The RS chart, however, is making higher lows or has recently turned up. This divergence — flat price with improving relative strength — often precedes a price breakout.

**Detection:** price chart shows no net progress over the last K columns (default K=10); RS chart shows a higher low or a recent buy signal in the same window.

**Why it's pre-momentum:** the RS line leads the price line in many sustained moves. A base with rising RS is a base where institutional buyers are accumulating ahead of the eventual breakout.

---

## Stocks already in momentum (NOT excluded — see [in-momentum-detection.md](in-momentum-detection.md))

**Updated 2026-05-16:** Per the advisor, stocks that are already in strong momentum are *not* excluded from the report. They are still useful to him — sometimes he does want to buy into existing strength. They appear in **Section B of the daily report**, separately from the Section A pre-momentum candidates. See [in-momentum-detection.md](in-momentum-detection.md) for the in-momentum patterns, anti-patterns (exhaustion/blow-off signals), and scoring framework.

The pre-momentum detector's job here is just to **classify** — does this stock match a pre-momentum setup (Section A) or an in-momentum setup (Section B)? Stocks that match neither are not surfaced. Stocks that match both go to Section A by default.

---

## Freshness — pattern-fired-last-night is weighted heavily

Per advisor direction 2026-05-16, the bot weights patterns that fired *very recently* much more heavily than patterns that fired weeks ago. A bullish triangle that resolved into a breakout *last night* is far more actionable than the same pattern that fired three weeks ago — the price has had time to extend by then.

**Freshness contribution to the score:**

| Pattern fired (trading days ago) | Score multiplier |
|---|---|
| 1 (last night's close) | ×2.0 (significant boost) |
| 2–3 | ×1.5 |
| 4–10 | ×1.0 (baseline) |
| 11–30 | ×0.7 (decayed) |
| > 30 | ×0.4 (stale; still surfaced if otherwise compelling) |

**New-last-night callout section in the report:** above Section A, the daily report opens with a **"New Patterns from Last Night"** highlight box listing every stock in the universe where any of the 7 pre-momentum patterns fired on the most recent trading day. These are the freshest opportunities and appear regardless of where they rank in the broader Section A composite score — the advisor sees them first because they are time-sensitive.

The freshness multiplier is layered on top of the composite score described below — it changes ranking, not pattern definition.

---

## Composite pre-momentum score

For each stock that passes the universe and liquidity filters, the bot computes a **pre-momentum score** combining the pattern signals above. Initial weights are best-guess and will be tuned via the backtest in Phase 4. The formula is transparent and additive so the advisor can always inspect why a name scored where it did.

| Component | Weight (initial) | What it captures |
|---|---|---|
| Pattern setup score | 0.30 | Which of the 7 pre-momentum patterns above are active (multiple can stack) |
| RS regime score | 0.20 | Is RS positive? Just turned positive? Strong vs sector? |
| Sector tailwind | 0.15 | Sector BPI state (Bull Confirmed, Bull Alert most favorable) |
| Distance-from-trendline score | 0.15 | Closer to 45° bullish support = higher; far above = lower |
| Time-in-base score | 0.10 | Longer consolidation before setup = higher conviction |
| TA score posture | ±0.10 | Medium TA score with setup is favorable; high TA score with extension is unfavorable |

The raw composite score is then **multiplied by the freshness factor** above, producing the final ranking score for Section A.

(Weights are illustrative and will be tuned. The point is the *shape*: pre-momentum patterns and regime changes drive the score; freshness amplifies; the anti-patterns inform Section B classification rather than exclusion.)

Stocks matching the anti-pattern (already-in-motion) criteria are **routed to Section B** rather than excluded — see [in-momentum-detection.md](in-momentum-detection.md) for the Section B scoring framework.

---

## Implementation roadmap

This methodology is implemented across phases per [00-project-outline.md](../00-project-outline.md):

- **Phase 2** builds the underlying P&F engine — chart construction, all signal detectors, trendlines, RS chart, BPI computation. The engine produces the structured chart classification (current signal, trend, RS state, etc.) for each stock.
- **Phase 4** wires the engine's outputs into the pre-momentum detectors and the composite score. The backtest validates whether the score has predictive power and tunes the weights.
- **Phase 5** renders the report, ranking candidates by pre-momentum score and showing each name's component breakdown so the advisor can understand *why* it ranked where it did.

---

## Open implementation questions (to settle as the engine is built)

These are not blocking now but will need answers during Phase 2 and Phase 4 implementation:

1. **Exact definition of "extended"** for the trendline-extension anti-pattern. 5 boxes? 10 boxes? Sector-dependent? Best determined by backtest.
2. **Long-base threshold** — how many sideways columns count as a "long base"? 10? 20? 30? Backtest will tell us.
3. **Time horizon for "near future" momentum** — the bot is predicting moves "in the near future," but is that 1 month, 3 months, 6 months? Backtest scoring should look at forward returns at multiple horizons and we tune to whichever shows the cleanest signal.
4. **How many candidates to surface per day** — top 10? Top 25? Top 50? Depends on how many high-quality setups typically exist in a ~6,000-name universe. Best-guess starting point: top 10, adjustable.

---

## References

- Dorsey, Thomas J., *Point and Figure Charting* — especially the chapters on long tails, catapults, triangles, Relative Strength, and Bullish Percent. These are the source for every pattern definition above.
- [methodology/point-and-figure.md](point-and-figure.md) — P&F construction and signal definitions
- [methodology/relative-strength.md](relative-strength.md) — RS construction and regime states
- [methodology/bullish-percent-index.md](bullish-percent-index.md) — BPI and the six market states
