# Project Outline

This is the canonical phased plan for the P&F + Fundamental Stock Screening Bot. Each phase has a clear deliverable that must exist before the next phase begins. Phases are not sized equally — Phase 0 is small but blocking; Phase 2 (the P&F engine) is the largest single chunk of work.

---

## Vision

A daily screening bot that scans a universe of US equities, applies P&F technical analysis alongside a fundamental quality filter, and emails the advisor a ranked report of *pre-breakout* candidates — stocks showing the technical and fundamental tells that typically precede a profitable move, identified before the move plays out.

The bot does not predict the future. It identifies setups that historically have favorable expected value, presented with full reasoning so the advisor can apply judgement.

---

## Phase 0 — Discovery & Compliance ✅ COMPLETE 2026-05-18

**Goal:** lock in scope, data sources, and compliance posture before any code is written.

**Resolved during Phase 0:**

1. ✅ Compliance scope cleared by the advisor before commissioning ([decisions log entry](01-decisions-log.md#2026-05-16--compliance-scope-already-cleared-by-the-advisor-resolves-oq-006))
2. ✅ DWA access path: **Norgate Data Platinum only** — no NDWEQTA, no manual DWA export ([decisions log entry](01-decisions-log.md#2026-05-18--dwa-access-path-final-norgate-only-resolves-oq-002))
3. ✅ Stock universe: full US equities, $1 minimum price floor
4. ✅ Fundamental filter removed entirely; pure P&F screener
5. ✅ Report cadence: daily, with two-section structure (pre-momentum + in-momentum) plus a "new patterns from last night" callout

**Estimated effort already spent:** ~0 developer hours coding. Phase 0 was discovery, decisions, and documentation — captured in the docs/ tree.

---

## Phase 1 — Data Foundation

**Goal:** establish the data pipeline. Norgate OHLC + universe definition flowing into a local SQLite store on a daily schedule.

**Tasks (with hour estimates):**

| # | Task | Est. hours |
|---|---|---|
| 1 | Norgate account setup, install Python SDK (`norgatedata` package), basic connectivity test | 1–2 |
| 2 | Universe loader — every US-listed common stock above $1 price floor, point-in-time aware for historical dates | 2–3 |
| 3 | SQLite schema + SQLAlchemy models (tickers, daily_bars, signal_state_history, reports_archive) | 3–4 |
| 4 | Price fetcher — daily OHLC for the universe, with 5+ year historical backfill | 3–5 |
| 5 | Data quality checks (no negative prices, gap detection, split-adjustment sanity) | 2–3 |
| 6 | Daily refresh scheduler (cron + Python entry point) | 1–2 |
| 7 | Smoke-test script: confirm universe loaded, OHLC current, no missing tickers | 1–2 |

**Phase 1 estimated effort: 13–21 developer hours.**

**Deliverable:** a one-command nightly job that refreshes Norgate data into the local store. Smoke test confirms every ticker in the universe has current OHLC.

---

## Phase 2 — P&F Analysis Engine

**Goal:** the technical core. Given a ticker, produce a P&F chart object and identify its current signal state, trendlines, RS rank, BPI context, and proximity to the next signal.

The largest phase. No production-grade open-source P&F library follows Dorsey's conventions faithfully, so we build it from scratch.

**Tasks (with hour estimates):**

| # | Task | Est. hours |
|---|---|---|
| 1 | Box scaling — Dorsey's traditional price-tiered table + percentage mode for RS charts; tier-boundary edge cases | 2–3 |
| 2 | P&F chart construction (high/low method) — column tracking, reversal logic, day-by-day update | 6–10 |
| 3 | Edge cases — sparse data, splits-adjusted reconciliation, tier crossings mid-column | 3–5 |
| 4 | Signal detector: Double Top / Double Bottom | 1–2 |
| 5 | Signal detector: Triple Top / Triple Bottom | 1–2 |
| 6 | Signal detector: Spread Triple Top / Spread Triple Bottom | 2–3 |
| 7 | Signal detector: Bullish / Bearish Catapult | 3–4 |
| 8 | Signal detector: Bullish / Bearish Triangle | 3–4 |
| 9 | Signal detector: Long tail (capitulation pattern) | 1–2 |
| 10 | 45° trendlines — bullish support, bearish resistance, automatic redrawing on new reversal extremes | 3–4 |
| 11 | Relative Strength — RS chart (price/SPXEWI × 100), 6.5% boxes, RS buy/sell signal detection | 4–6 |
| 12 | Bullish Percent Index — universe BPI + 11 GICS sector BPIs, plotted as P&F with 2% boxes, six-state classification | 3–5 |
| 13 | Proximity-to-signal — how many boxes from next buy/sell signal | 2–3 |
| 14 | Validation against textbook examples from Dorsey's book + advisor spot-checks | 4–6 |
| 15 | Unit test suite across all of the above | 6–10 |

**Phase 2 estimated effort: 44–69 developer hours.**

**Deliverable:** a Python module that, given a ticker, returns a structured object with the current P&F chart, signal history, current signal state, trendlines, RS state, sector BPI context, and proximity-to-next-signal — fully unit-tested.

---

## ~~Phase 3 — Fundamental Screening Engine~~ — REMOVED 2026-05-16

> **This phase was eliminated from the project on 2026-05-16.** The advisor determined fundamental screening adds no edge — the P&F chart already reflects fundamentals via supply and demand. The bot is now a pure P&F screener.
>
> See [decisions log entry](01-decisions-log.md#2026-05-16--fundamental-filter-removed-entirely-supersedes-the-oq-004-default) and the superseded [methodology/fundamental-screen.md](methodology/fundamental-screen.md).
>
> The project now skips directly from Phase 2 (P&F Analysis Engine) to Phase 4 (Pre-Momentum Scoring & Detection).

---

## Phase 4 — Pre-Momentum + In-Momentum Scoring & Detection

**Goal:** the heart of the bot. Apply the pre-momentum + in-momentum detection methodology to classify and rank stocks.

**Tasks (with hour estimates):**

| # | Task | Est. hours |
|---|---|---|
| 1 | Pre-momentum pattern detector: Bullish triangle near breakout | 2–3 |
| 2 | Pre-momentum pattern detector: Long tail reversal + initial buy signal | 2–3 |
| 3 | Pre-momentum pattern detector: First buy signal after extended sell regime | 1–2 |
| 4 | Pre-momentum pattern detector: Bullish catapult setup forming | 2–3 |
| 5 | Pre-momentum pattern detector: RS turning positive | 1–2 |
| 6 | Pre-momentum pattern detector: Sector BPI inflection from below 30% | 2–3 |
| 7 | Pre-momentum pattern detector: Sideways base with rising RS | 2–3 |
| 8 | In-momentum pattern detectors (6 patterns) | 6–10 |
| 9 | Anti-pattern / exhaustion exclusions (parabolic, blow-off, far above trendline) | 2–3 |
| 10 | Internal TA-equivalent composite score (0–5) — our self-built version of DWA's TA score | 2–3 |
| 11 | Composite scoring (pre-momentum + in-momentum, with all weighted components) | 3–5 |
| 12 | Freshness multiplier framework (recent-pattern boost) | 1–2 |
| 13 | "New patterns last night" detection logic | 1–2 |
| 14 | Backtest harness — replay history, forward-return measurement at 1/3/6/12 month horizons | 8–12 |
| 15 | Backtest metrics — hit rate, avg winner, avg loser, max drawdown, Sharpe, by section and by pattern | 4–6 |
| 16 | Weight tuning via backtest with out-of-sample validation year | 4–6 |

**Phase 4 estimated effort: 43–68 developer hours.**

**Deliverable:** given any date, a ranked list of pre-momentum and in-momentum candidates with full reasoning per the methodology docs, plus a documented backtest demonstrating the screen's historical behavior at multiple forward horizons.

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

**Tasks (with hour estimates):**

| # | Task | Est. hours |
|---|---|---|
| 1 | P&F chart renderer (matplotlib) — Xs/Os, trendlines, signal annotations, Dorsey visual conventions | 6–10 |
| 2 | RS chart renderer — percentage-scaling P&F, same conventions | 2–3 |
| 3 | Per-stock detail compiler — gather all 15 elements per candidate into a structured record | 4–6 |
| 4 | Jinja2 HTML report template — "New Last Night" callout + Section A + Section B + per-stock blocks | 4–6 |
| 5 | WeasyPrint HTML → PDF generation | 2–3 |
| 6 | Email delivery — SMTP or transactional provider, attachment handling | 2–3 |
| 7 | Audit log + report archive (timestamp, full contents, parameter snapshot) | 2–3 |
| 8 | Pattern reasoning narrative generator (the per-stock prose explanation) | 3–5 |

**Phase 5 estimated effort: 25–39 developer hours.**

**Deferred to post-launch (Phase 6 or beyond):** internal web dashboard for ad-hoc exploration. Not needed for v1.

**Deliverable:** the advisor receives a structured daily report each morning before market open, with the three top-level segments and extensive per-stock detail. Every report is archived.

---

## Phase 6 — Feedback Loop

**Goal:** the bot improves over time. Track what works and what doesn't.

**Tasks (with hour estimates):**

| # | Task | Est. hours |
|---|---|---|
| 1 | Recommendation tracker — tag every name surfaced, record its forward performance | 3–4 |
| 2 | Scoreboard — weekly/monthly stats on actual live recommendations (hit rate, winners/losers, drawdown) | 3–5 |
| 3 | Weight retuning workflow — periodic re-fit based on live recommendation outcomes | 2–3 |
| 4 | Pattern expansion as advisor identifies edge cases the bot misses | ongoing |

**Phase 6 estimated effort: 8–12 developer hours** for the initial implementation; pattern expansion is ongoing post-launch.

**Deliverable:** an evergreen tuning loop that keeps the bot calibrated against live market conditions.

---

## Total effort estimate

Adding up the phase ranges (all estimates assume developer working with AI assistance for code generation, testing, and debugging):

| Phase | Range (hours) |
|---|---|
| Phase 0 — Discovery & Compliance | ✅ complete |
| Phase 1 — Data Foundation | 13–21 |
| Phase 2 — P&F Analysis Engine | 44–69 |
| Phase 3 — REMOVED | 0 |
| Phase 4 — Scoring & Detection (incl. backtest) | 43–68 |
| Phase 5 — Reporting & Delivery | 25–39 |
| Phase 6 — Feedback Loop (initial) | 8–12 |
| **Total remaining build effort** | **133–209 hours** |

### Milestone breakdown — what the advisor gets at each spending milestone

If the advisor wants to fund this in tranches and see working output before committing the full budget, here is a sensible milestone progression:

| Milestone | What it delivers | Cumulative hours |
|---|---|---|
| **M1: Working data pipeline** | Norgate OHLC flowing daily into local store; universe loaded; smoke test green | 13–21 |
| **M2: P&F engine MVP** | Engine constructs charts, detects basic signals (DT/DB/TT/TB), draws trendlines, computes RS — for any individual ticker | 33–54 |
| **M3: Full P&F engine + BPI** | All 8 signal types, full RS framework, universe-wide BPI + sector BPIs, validated against textbook examples | 57–90 |
| **M4: Demo screen (no backtest yet)** | Bot produces a ranked daily list of pre-momentum + in-momentum candidates with initial weights — viewable as JSON or HTML | 85–135 |
| **M5: Backtest + tuned weights** | Backtest harness operational, weights tuned against historical performance, out-of-sample validated | 100–155 |
| **M6: Full v1 daily PDF report delivered to inbox** | Complete report with charts, per-stock detail, email delivery, audit archive | 125–194 |
| **M7: Feedback loop running** | Live recommendation tracking + scoreboard | 133–209 |

### How to interpret these ranges

- **Lower bound** assumes everything goes smoothly: clean APIs from Norgate, well-defined patterns translate cleanly to code, no major debugging surprises.
- **Upper bound** assumes realistic friction: data-quality edge cases, P&F signal definitions that are ambiguous in places and need iterating, validation against the book takes longer than expected.
- **Both bounds assume the developer is working with AI assistance** (Claude for code generation, methodology questions, debugging, and test writing). Without AI assistance, multiply by roughly 1.5–2×.
- These are *development* hours only — they do not include: the advisor's review time, the advisor's daily use of the bot, ongoing data subscription costs, or post-launch maintenance.

### The right place to pause and reassess

A good gate for the advisor's review is **M4 (the demo screen)**. At ~85–135 hours cumulative, the bot will be producing a ranked daily output. The advisor can review the output, sanity-check whether the candidates make sense to him given his manual P&F work, and decide whether to continue funding the remaining ~50–75 hours through full v1.

---

## Cross-cutting concerns

These apply to every phase and are not standalone work items, but they need attention throughout:

- **Documentation** — every meaningful design decision and finding goes into `docs/` and into the decisions log. See [01-decisions-log.md](01-decisions-log.md).
- **Testing** — every public function gets unit tests; the P&F engine especially needs test fixtures derived from textbook examples.
- **Auditability** — every report and every data refresh is logged. The advisor must be able to answer "why was XYZ recommended on date D?" months later.
- **Disclaimers** — every report carries a disclaimer that it is an internal idea-generation tool, not investment advice. See [compliance.md](compliance.md).
