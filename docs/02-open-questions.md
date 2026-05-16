# Open Questions

Items that require client input, further research, or decisions before they unblock work downstream. This document is curated — when an item is resolved, move the resolution into [01-decisions-log.md](01-decisions-log.md) and remove the item from here (or strike it through with a link to the decision).

Each item is tagged with:
- **Blocking?** — does any current or near-term work depend on resolving this?
- **Owner** — who is responsible for the answer (advisor, developer, compliance officer)
- **Asked** — date first raised
- **Notes** — relevant context

---

## OQ-001: Box scaling confirmation

- **Question:** Confirm that we use Dorsey's traditional price-tiered box scaling for stock price charts. (Recommended in [methodology/point-and-figure.md](methodology/point-and-figure.md).)
- **Blocking?** No (default to traditional unless overridden — but lock this in before Phase 2 chart-construction work begins)
- **Owner:** Advisor
- **Asked:** 2026-05-15
- **Notes:** Traditional scaling matches Dorsey's book and the DWA platform default. Percentage scaling is reserved for RS charts.

---

## OQ-002: DWA access path

- **Question:** Which of the three viable DWA access paths do we use?
  - **A.** License the Nasdaq Data Link NDW database (highest fidelity, paid, requires sales quote)
  - **B.** Manual CSV exports from the existing NDW Research Platform subscription (high fidelity, no extra cost, requires manual step daily/weekly)
  - **C.** Replicate from raw OHLC using publicly documented methodology (good fidelity, no DWA cost, most flexible)
- **Blocking?** Yes for Phase 1
- **Owner:** Advisor (decision); Developer (analysis already done in [research/dwa-access.md](research/dwa-access.md))
- **Asked:** 2026-05-15
- **Notes:** Claude's recommendation is C for v1, with the option to layer A as a verification feed in v2. The proprietary "DWA Technical Attributes" composite score is the main thing C gives up — worth asking whether the advisor actually uses that score in their workflow.

---

## OQ-003: Stock universe

- **Question:** What universe of tickers does the bot evaluate?
  - **A.** Russell 3000 (≈3,000 names — large + mid + small caps)
  - **B.** S&P 1500 (≈1,500 names — large + mid + small caps with stronger liquidity filter)
  - **C.** Full US listed (NYSE + NASDAQ filtered by minimum price and volume — ≈4,000–5,000 names)
  - **D.** A custom watchlist the advisor maintains
- **Blocking?** Yes for Phase 1
- **Owner:** Advisor
- **Asked:** 2026-05-15
- **Notes:** Claude's recommendation is Russell 3000 to start. It's broad enough to surface non-obvious names, narrow enough to keep compute tractable and to align with how DWA itself indexes the equity universe.

---

## OQ-004: Fundamental filter criteria

- **Question:** What does the fundamental filter actually screen on? Some shapes to choose from:
  - **A.** Quality gate only (positive FCF, manageable debt, positive ROE)
  - **B.** Quality + growth (A plus positive revenue/EPS growth over TTM)
  - **C.** Quality + growth + reasonable valuation (B plus industry-relative P/E or PEG within bounds)
  - **D.** Custom set the advisor uses today
- **Blocking?** Yes for Phase 3
- **Owner:** Advisor
- **Asked:** 2026-05-15
- **Notes:** Per Dorsey's view, this is a junk-rejection gate, not a primary signal. Recommend keeping it narrow — option A or B. Detailed shape captured in [methodology/fundamental-screen.md](methodology/fundamental-screen.md).

---

## OQ-005: Report cadence and delivery

- **Question:** When does the advisor get the report and in what format?
  - Default working assumption: daily PDF email after market close (or pre-market the next day), plus a weekly summary on Sundays
- **Blocking?** Not immediately, but needs to be settled before Phase 5
- **Owner:** Advisor
- **Asked:** 2026-05-15
- **Notes:** PDF email is the lowest-friction format. An internal web dashboard could be added later if the advisor wants to drill in.

---

## OQ-006: Compliance officer sign-off

- **Question:** Does the firm's compliance officer agree that this tool — strictly internal, advisor-only, no client-facing output, no trade execution — is in scope for normal advisor workflow and does not require additional registration, disclosure, or recordkeeping beyond standard practice?
- **Blocking?** Yes — should be answered before any production data is wired up
- **Owner:** Advisor (to consult their compliance officer)
- **Asked:** 2026-05-15
- **Notes:** Even though our compliance posture is conservative (internal-only, no advice, no trades), confirming this with the firm's compliance officer protects everyone. Capture the conversation in writing for the audit trail.

---

## OQ-007: Backtest universe and look-back window

- **Question:** How many years of historical data should the backtest cover, and should the universe be "Russell 3000 as it stood on each historical date" (point-in-time) or "Russell 3000 as it stands today" (which introduces survivorship bias)?
- **Blocking?** Not immediately — relevant for Phase 4
- **Owner:** Developer (analysis) + Advisor (decision)
- **Asked:** 2026-05-15
- **Notes:** Point-in-time is the rigorous choice but requires a historical constituent list from the data vendor. Survivorship-biased backtest is faster to set up but overstates real-world performance. Decide in Phase 4.

---

## OQ-008: Does the advisor use DWA's "Technical Attributes" composite score?

- **Question:** In the advisor's actual workflow, do they rely on DWA's proprietary "Technical Attributes" composite score, or do they primarily look at the underlying signals (current P&F signal, RS, trend, etc.)?
- **Blocking?** No — but the answer affects whether the recommendation in OQ-002 stands
- **Owner:** Advisor
- **Asked:** 2026-05-15
- **Notes:** If the score is central, the case for option A (licensing the NDW Data Link database) gets much stronger. If the advisor mostly looks at underlying signals, replicating from raw OHLC is sufficient.
