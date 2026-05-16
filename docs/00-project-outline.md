# Project Outline

This is the canonical phased plan for the P&F + Fundamental Stock Screening Bot. Each phase has a clear deliverable that must exist before the next phase begins. Phases are not sized equally — Phase 0 is small but blocking; Phase 2 (the P&F engine) is the largest single chunk of work.

---

## Vision

A daily screening bot that scans a universe of US equities, applies P&F technical analysis alongside a fundamental quality filter, and emails the advisor a ranked report of *pre-breakout* candidates — stocks showing the technical and fundamental tells that typically precede a profitable move, identified before the move plays out.

The bot does not predict the future. It identifies setups that historically have favorable expected value, presented with full reasoning so the advisor can apply judgement.

---

## Phase 0 — Discovery & Compliance

**Status:** in progress (started 2026-05-15)

**Goal:** lock in scope, data sources, and compliance posture before any code is written. This phase is short but its outputs constrain everything that follows.

**Tasks:**
1. Compliance review with the firm's compliance officer. Confirm that an internal-only screening tool that does not produce client-facing material and does not place trades does not trigger additional registration, disclosure, or recordkeeping requirements beyond standard advisor workflow. Document the conversation.
2. Confirm Dorsey Wright access mechanics (research already completed — see [research/dwa-access.md](research/dwa-access.md)). Decision pending on whether to (a) license Nasdaq Data Link's NDW database, (b) rely on manual CSV exports from the existing NDW Research Platform subscription, or (c) replicate the methodology from raw OHLC.
3. Define the stock universe. Recommended starting point: Russell 3000 (≈3,000 large + mid + small caps). Alternatives: S&P 1500, NYSE+NASDAQ filtered by minimum price and average volume.
4. ~~Define the fundamental initial-filter criteria with the advisor.~~ **REMOVED 2026-05-16** — fundamental filter eliminated entirely from project scope. See [decisions log](01-decisions-log.md#2026-05-16--fundamental-filter-removed-entirely-supersedes-the-oq-004-default).
5. Define report cadence and delivery format. **Daily report** confirmed 2026-05-16.

**Deliverable:** a one-page scope agreement covering compliance posture, data sources, universe, and report cadence — signed off by the advisor before Phase 1 starts.

---

## Phase 1 — Data Foundation

**Goal:** establish the data pipeline that feeds every subsequent phase. Prices, fundamentals, and (if chosen) DWA data flow into a queryable local store on a daily schedule.

**Tasks:**
1. Stand up a data vendor account. Working recommendation: **Polygon.io Stocks Starter** or **Tiingo** for end-of-day OHLC across the full US equity universe (~6,000 names). See [data-sources.md](data-sources.md) for the full evaluation.
2. ~~Stand up a fundamentals vendor.~~ **REMOVED 2026-05-16** — fundamental filter eliminated from project scope.
3. Implement the **universe loader** — produce a list of US-listed common stock tickers passing the $1 minimum price floor (see [OQ-009 resolution](01-decisions-log.md#2026-05-16--universe-liquidity-floor-1-minimum-price-no-explicit-volume-floor-resolves-oq-009)).
4. Implement the **price fetcher** — daily OHLC for every ticker in the universe, stored in a local database. Backfill at least 5 years of history.
5. ~~Implement the fundamentals fetcher.~~ **REMOVED 2026-05-16** — no fundamentals in scope.
6. (Conditional on Phase 0 decision per [OQ-002](02-open-questions.md#oq-002-dwa-access-path--provisionally-resolved-2026-05-16-pending-pricing)) Implement either the **Nasdaq Data Link NDWEQTA ingester** (if pricing is acceptable) or the full **OHLC-based replication path** per [research/ndw-data-link-alternatives.md](research/ndw-data-link-alternatives.md).
7. Implement a **scheduler** — a daily cron job that refreshes all data after market close.

**Deliverable:** a one-command nightly job that refreshes all data, with a smoke test confirming each ticker in the universe has current OHLC.

---

## Phase 2 — P&F Analysis Engine

**Goal:** the technical core. Given a ticker, produce a P&F chart object and identify its current signal state, trendlines, RS rank, and proximity to the next signal.

This phase is the largest. No production-grade open-source P&F library exists in Python that follows Dorsey's conventions faithfully, so we build it.

**Tasks:**
1. Implement **box scaling** per Dorsey's traditional table for price charts, plus a percentage-scaling mode for RS charts. See [methodology/point-and-figure.md](methodology/point-and-figure.md) for the table.
2. Implement **P&F chart construction** from OHLC. The algorithm uses high/low method (Dorsey's preferred): in an X column, if today's high exceeds the next box, extend the column up; if today's low is more than 3 boxes below, reverse to an O column at the appropriate level. Mirror logic for O columns.
3. Implement **signal detectors** — one function per signal type, returning the column index and price level at which the signal fired. Cover: double top, double bottom, triple top, triple bottom, spread triple top/bottom, bullish/bearish catapult, bullish/bearish triangle, long tail. See [methodology/point-and-figure.md](methodology/point-and-figure.md).
4. Implement **45° trendlines** — bullish support and bearish resistance, drawn per Dorsey's rules from the most recent reversal extreme.
5. Implement **Relative Strength** — RS chart = (stock price / SPXEWI) × 100, plotted as P&F with 6.5% box and 3-box reversal. Detect long-term RS buy/sell signals. See [methodology/relative-strength.md](methodology/relative-strength.md).
6. Implement **proximity-to-signal** — given a current chart state, how many boxes away is the next buy or sell signal? This is the key input to the "pre-breakout" detector in Phase 4.
7. Implement **Bullish Percent Index (BPI)** for the chosen universe and for sectors. See [methodology/bullish-percent-index.md](methodology/bullish-percent-index.md).
8. **Validation:** cross-check the engine's output against either (a) DWA platform charts if Phase 0 chose CSV-export path, or (b) a known set of textbook examples from Dorsey's book. Document any divergence.

**Deliverable:** a Python module that, given a ticker, returns a structured object with the current P&F chart, signal history, current signal state, trendlines, RS state, and proximity-to-next-signal — fully unit-tested.

---

## ~~Phase 3 — Fundamental Screening Engine~~ — REMOVED 2026-05-16

> **This phase was eliminated from the project on 2026-05-16.** The advisor determined fundamental screening adds no edge — the P&F chart already reflects fundamentals via supply and demand. The bot is now a pure P&F screener.
>
> See [decisions log entry](01-decisions-log.md#2026-05-16--fundamental-filter-removed-entirely-supersedes-the-oq-004-default) and the superseded [methodology/fundamental-screen.md](methodology/fundamental-screen.md).
>
> The project now skips directly from Phase 2 (P&F Analysis Engine) to Phase 4 (Pre-Momentum Scoring & Detection).

---

## Phase 4 — Pre-Momentum Scoring & Detection

**Goal:** the heart of the bot. Apply the pre-momentum detection methodology ([methodology/pre-momentum-detection.md](methodology/pre-momentum-detection.md)) to surface stocks at the *start* of a potential move — before momentum develops — not stocks already in motion.

**Tasks:**
1. Implement the **pre-momentum pattern detectors** — one function per pattern from the pre-momentum methodology doc:
   - Bullish triangle near breakout
   - Long tail down reversal followed by initial buy signal
   - First buy signal after an extended sell-signal regime
   - Bullish catapult setup forming (not yet fired)
   - Long-term RS turning positive
   - Sector BPI inflection from below 30%
   - Sideways base with rising RS underneath
2. Implement the **anti-pattern exclusions** — hard-exclude stocks matching any "already in momentum" criteria (extended above trendline, recent buy signal that has rallied, parabolic X column, high TA score combined with extension).
3. Implement the **composite pre-momentum score** — weighted combination of pattern setup score, RS regime score, sector tailwind, distance-from-trendline, time-in-base, and TA score penalty. Initial weights are best-guess (see methodology doc); tune in step 5.
4. Implement the **backtest harness** — replay the past N years, simulating the screener as it would have run each day. For each date, generate the top-K candidates. Measure forward returns at standard horizons (1 month, 3 months, 6 months, 12 months). The key question the backtest must answer: do stocks the bot flagged as pre-momentum candidates actually outperform in the weeks/months *after* being flagged? Report hit rate, average winner, average loser, max drawdown, Sharpe.
5. **Tune** the composite weights using backtest results. Reserve a final out-of-sample year and confirm the tuned weights still perform on that year.

**Deliverable:** given any date, a ranked list of pre-momentum candidates with full reasoning per the methodology doc, plus a documented backtest demonstrating the screen's historical behavior at multiple forward horizons.

---

## Phase 5 — Reporting & Delivery

**Goal:** the daily artifact that lands in the advisor's inbox.

**Report structure (per advisor direction 2026-05-16):**

The daily report has three top-level segments:

**0. New Patterns from Last Night** — a callout at the top of the report listing every stock where any of the 7 pre-momentum patterns *fired on the most recent trading day*. These are time-sensitive opportunities and lead the report regardless of where they sit in the broader composite ranking. Each name appears with the pattern that fired, the date/box level, and a one-line context.

**Section A — Pre-Momentum Candidates** — the main attraction. Stocks identified by the pre-momentum methodology ([methodology/pre-momentum-detection.md](methodology/pre-momentum-detection.md)) as being at the start of a potential move. Default: top 25 by composite pre-momentum score.

**Section B — In-Momentum Candidates** — stocks already in strong, sustainable momentum that the advisor may still want to buy into. Curated per [methodology/in-momentum-detection.md](methodology/in-momentum-detection.md); excludes parabolic/blow-off names. Default: top 25 by composite in-momentum score.

**Per-stock detail (extensive, applies to every entry in Section A and B):**

Each candidate's report block includes:

1. **Ticker, company name, sector, current price.**
2. **Section / category classification.** (Section A or B; primary pattern matched.)
3. **Composite score** with full component breakdown: pattern score, RS regime score, sector tailwind, distance-from-trendline, time-in-base, TA score contribution, freshness multiplier.
4. **P&F chart image** (custom rendered, Dorsey conventions: Xs in green/black, Os in red, bullish support and bearish resistance lines, signal annotations).
5. **RS chart image** versus SPXEWI/RSP — same P&F conventions, percentage scaling.
6. **Current signal state:** type, date fired, price level, distance from current price.
7. **Recent signal history** — the previous 3–5 signals with dates and price levels, so the advisor can see how the chart has evolved.
8. **Pattern reasoning** — narrative explanation of *which* pre-momentum or in-momentum patterns matched and *why*. For example: "This name fired its first buy signal after an 18-month sell-signal regime on 2026-05-15. The long-term RS chart turned positive 6 weeks earlier. The sector BPI is in Bull Alert state. Distance from current price to the bullish support line is 4 boxes ($3 risk on a $48 stock = 6.3%)."
9. **RS posture:** current RS rank in universe, current RS rank in sector, RS chart state (buy/sell signal), recent direction.
10. **Sector context:** GICS sector, sector BPI value and state, sector RS posture.
11. **Trend posture:** above or below bullish support line, distance from trendline, time in current trend.
12. **Suggested entry zone** — the price range where adding makes sense, typically the current box and the one above.
13. **Suggested P&F stop level** — the box one below the current bullish support line, or one below a recent O column low.
14. **Pre-momentum or in-momentum specific notes:**
    - For pre-momentum names: time-in-base, how many boxes from the next buy signal, what would trigger the breakout
    - For in-momentum names: how recent the breakout was, how extended the chart is, when the next anti-pattern threshold would be triggered
15. **(If NDWEQTA is in use) DWA fields:** Technical Attributes score (0–5), DWA sector classification, signal status as DWA reports it (for cross-check).

**Tasks:**
1. Implement the **chart renderer** — produce P&F chart images per Dorsey's visual conventions. Both price charts and RS charts.
2. Implement the **per-stock detail compiler** — for each candidate, gather all 15 elements listed above and produce a structured record.
3. Implement the **report template** — Jinja2 HTML template containing: the New-Last-Night callout, Section A, Section B, and per-stock detail blocks. Mobile-readable but optimized for desktop / PDF reading.
4. Implement **PDF generation** via WeasyPrint.
5. Implement **email delivery** — SMTP or transactional email provider, sending the report to the advisor each morning before market open.
6. Implement the **audit log** — every report generated is archived to disk with timestamp, full contents, and the parameter snapshot that produced it. Required for the audit record per [compliance.md](compliance.md).
7. (Optional, later) A small **internal dashboard** — a local web app that lets the advisor explore the screen for any date, drill into individual tickers, and review backtest results.

**Deliverable:** the advisor receives a structured daily report each morning before market open, with the three top-level segments and extensive per-stock detail. Every report is archived.

---

## Phase 6 — Feedback Loop

**Goal:** the bot improves over time. Track what works and what doesn't.

**Tasks:**
1. Implement a **recommendation tracker** — every name surfaced by the bot is tagged and its forward performance recorded.
2. Implement a **scoreboard** — weekly/monthly stats on the bot's actual recommendations: hit rate, average gain on winners, average loss on losers, drawdown.
3. Periodic **weight retuning** based on what the bot is actually surfacing in live use, not just on backtest.
4. Add new signals or patterns as the advisor identifies edge cases the bot misses.

**Deliverable:** an evergreen tuning loop that keeps the bot calibrated against live market conditions.

---

## Cross-cutting concerns

These apply to every phase and are not standalone work items, but they need attention throughout:

- **Documentation** — every meaningful design decision and finding goes into `docs/` and into the decisions log. See [01-decisions-log.md](01-decisions-log.md).
- **Testing** — every public function gets unit tests; the P&F engine especially needs test fixtures derived from textbook examples.
- **Auditability** — every report and every data refresh is logged. The advisor must be able to answer "why was XYZ recommended on date D?" months later.
- **Disclaimers** — every report carries a disclaimer that it is an internal idea-generation tool, not investment advice. See [compliance.md](compliance.md).
