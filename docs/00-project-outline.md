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

**Tasks:**
1. Implement the **chart renderer** — produce a P&F chart image per candidate using matplotlib or Plotly. Mirror Dorsey's visual conventions (Xs and Os, trendlines, signal labels).
2. Implement the **report template** — Jinja2 HTML template containing: top N candidates, P&F chart, RS chart, fundamental snapshot, suggested entry and P&F stop, one-paragraph rationale, links to source data.
3. Implement **PDF generation** via WeasyPrint.
4. Implement **email delivery** — SMTP or transactional email provider, sending the report to the advisor pre-market each weekday.
5. Implement the **audit log** — every report generated is archived to disk with timestamp, contents, and the parameter snapshot that produced it. Required for compliance.
6. (Optional, later) A small **internal dashboard** — a local web app that lets the advisor explore the screen for any date, drill into individual tickers, and review backtest results.

**Deliverable:** the advisor receives a usable PDF report each morning before market open, and every report is archived.

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
