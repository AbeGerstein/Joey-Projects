# Open Questions

Items that require client input, further research, or decisions before they unblock work downstream. This document is curated — when an item is resolved, move the resolution into [01-decisions-log.md](01-decisions-log.md) and remove the item from here (or strike it through with a link to the decision).

Each item is tagged with:
- **Blocking?** — does any current or near-term work depend on resolving this?
- **Owner** — who is responsible for the answer (advisor, developer, compliance officer)
- **Asked** — date first raised
- **Notes** — relevant context

---

## ~~OQ-001: Box scaling confirmation~~ — RESOLVED 2026-05-16

- **Resolution:** Use Dorsey's traditional price-tiered box-scaling table for price charts. See [decisions log 2026-05-16](01-decisions-log.md#2026-05-16--box-scaling-dorseys-traditional-table-for-price-charts-resolves-oq-001).

---

## OQ-002: DWA access path — PROVISIONALLY RESOLVED 2026-05-16 (pending pricing)

- **Resolution:** Option A — license the Nasdaq Data Link NDW database. Provisional, pending Nasdaq Data Link pricing quote and confirmation of coverage. See [decisions log 2026-05-16](01-decisions-log.md#2026-05-16--dwa-access-path-nasdaq-data-link-ndw-database-provisional-pending-pricing-partial-oq-002) and forthcoming [research/ndw-data-link-pricing.md](research/ndw-data-link-pricing.md).
- **Still open:** Final cost confirmation. If pricing exceeds the project budget, options B (manual export) or C (replicate) come back on the table — though both have downsides at this point (B incompatible with daily cadence, C missing the Technical Attributes score the advisor relies on).

---

## ~~OQ-003: Stock universe~~ — RESOLVED 2026-05-16

- **Resolution:** Full US equities universe (NYSE + NASDAQ common stocks). Minimum liquidity filter to be defined separately (see [OQ-009](#oq-009-liquidity-floor-for-the-universe)). See [decisions log 2026-05-16](01-decisions-log.md#2026-05-16--universe-full-us-equities-used-for-both-screening-and-backtesting-resolves-oq-003-and-oq-007).

---

## OQ-004: Fundamental filter criteria — PROVISIONALLY DEFAULTED 2026-05-16

- **Question:** What does the fundamental filter actually screen on?
  - **A.** Quality gate only (positive FCF, manageable debt, positive ROE) — **provisionally adopted**
  - **B.** Quality + growth (A plus positive revenue/EPS growth over TTM)
  - **C.** Quality + growth + reasonable valuation (B plus industry-relative P/E or PEG within bounds)
  - **D.** Custom set the advisor uses today
- **Status:** Provisionally defaulted to Option A on 2026-05-16 ([decisions log entry](01-decisions-log.md#2026-05-16--fundamental-filter-shape-option-a-quality-gate-only-provisional--defaulted-not-explicitly-confirmed)). Advisor did not explicitly answer this question and the default was applied to keep work unblocked.
- **Blocking?** Was blocking Phase 3 — now unblocked by the default, but advisor should confirm or override before Phase 3 implementation begins.
- **Owner:** Advisor
- **Asked:** 2026-05-15; defaulted 2026-05-16
- **Notes:** Recommendation stands: keep this narrow — the filter's job is junk rejection, not stock-picking on a fundamental basis. Particularly important now that the universe is full US equities and includes many structurally broken microcap names.

---

## ~~OQ-005: Report cadence~~ — RESOLVED 2026-05-16

- **Resolution:** Daily report. See [decisions log 2026-05-16](01-decisions-log.md#2026-05-16--report-cadence-daily-resolves-oq-005). Exact delivery format and timing to be finalized in Phase 5.

---

## ~~OQ-006: Compliance officer sign-off~~ — RESOLVED 2026-05-16

- **Resolution:** Treated as already cleared by the advisor — see [decisions log entry 2026-05-16](01-decisions-log.md#2026-05-16--compliance-scope-already-cleared-by-the-advisor-resolves-oq-006).
- **Caveat:** Resolution covers the current scope only (internal-only, advisor-only, no trade execution). If scope changes — particularly toward any client-facing output — this question reopens.

---

## ~~OQ-007: Backtest universe~~ — RESOLVED 2026-05-16

- **Resolution:** Same as the screening universe — full US equities. See [decisions log 2026-05-16](01-decisions-log.md#2026-05-16--universe-full-us-equities-used-for-both-screening-and-backtesting-resolves-oq-003-and-oq-007).
- **Still open:** point-in-time vs survivorship-biased backtest — the *handling* of the historical universe. Recommendation is point-in-time (rigorous, no survivorship bias), which requires historical constituent data. To be settled when Phase 4 begins.

---

## ~~OQ-008: DWA Technical Attributes score usage~~ — RESOLVED 2026-05-16

- **Resolution:** Yes — the advisor uses the Technical Attributes score and the full DWA toolset; the bot must include the same. See [decisions log 2026-05-16](01-decisions-log.md#2026-05-16--advisor-relies-on-dwa-technical-attributes-score-and-the-full-dwa-toolset-resolves-oq-008).
- **Implication:** Drives OQ-002 toward Option A (Nasdaq Data Link) — the Technical Attributes score is not replicable from raw OHLC.

---

## OQ-009: Liquidity floor for the universe

- **Question:** Now that the universe is "all US equities," we need a minimum-liquidity filter to exclude truly untradeable names (penny stocks, illiquid microcaps the advisor can't realistically transact in). What thresholds?
  - **A.** Minimum price $1, minimum 20-day average dollar volume $100K — permissive, includes most microcaps
  - **B.** Minimum price $5, minimum 20-day average dollar volume $1M — moderate, excludes penny stocks
  - **C.** Minimum price $10, minimum 20-day average dollar volume $5M — strict, focuses on liquid mid-caps and above
  - **D.** No filter — evaluate every listed common stock the data vendor returns
- **Blocking?** Not immediately, but needs an answer before Phase 1 universe definition is finalized
- **Owner:** Advisor
- **Asked:** 2026-05-16 (new question, arose from the full-US-equities universe decision)
- **Notes:** The advisor's typical client position sizes drive the right answer here — if they routinely place orders that are large relative to a microcap's daily volume, they need a higher floor. Recommendation: Option B as a sensible default, easily adjustable later.
