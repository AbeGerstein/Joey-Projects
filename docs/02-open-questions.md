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

## ~~OQ-002: DWA access path~~ — RESOLVED 2026-05-18

- **Resolution:** Norgate Data Platinum only. No NDWEQTA, no manual DWA export, no DWA data in the bot's pipeline. The advisor's existing DWA platform subscription remains his personal cross-check tool. See [decisions log 2026-05-18](01-decisions-log.md#2026-05-18--dwa-access-path-final-norgate-only-resolves-oq-002).
- **Cost:** $53/mo Norgate + ~$10/mo hosting = ~$63/mo total, deferred until build hours are scoped.

---

## ~~OQ-003: Stock universe~~ — RESOLVED 2026-05-16

- **Resolution:** Full US equities universe (NYSE + NASDAQ common stocks). Minimum liquidity filter to be defined separately (see [OQ-009](#oq-009-liquidity-floor-for-the-universe)). See [decisions log 2026-05-16](01-decisions-log.md#2026-05-16--universe-full-us-equities-used-for-both-screening-and-backtesting-resolves-oq-003-and-oq-007).

---

## ~~OQ-004: Fundamental filter criteria~~ — RESOLVED 2026-05-16 (filter REMOVED)

- **Resolution:** Fundamental filter is removed from the project entirely. The bot is a pure P&F screener with no fundamental criteria applied. See [decisions log 2026-05-16](01-decisions-log.md#2026-05-16--fundamental-filter-removed-entirely-supersedes-the-oq-004-default).
- **Rationale:** Advisor's view (relayed by user 2026-05-16): if fundamentals on a stock are bad, buyers stay away and the P&F chart already shows it — a separate fundamental filter is redundant. Consistent with Dorsey's thesis that the chart reflects all inputs including fundamentals.

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
- **Still open:** point-in-time vs survivorship-biased backtest — the *handling* of the historical universe. Recommendation is point-in-time (rigorous, no survivorship bias), which requires historical constituent data. Norgate Data Platinum (already the working OHLC choice) includes survivorship-bias-free constituent history back to 1990 — this resolves cleanly if we go with Norgate.
- **Note on data-path implications:** the backtest's data requirement is historical OHLC + the bot's own engine running on it. It does NOT require historical DWA signal series. All three data paths (Norgate-only, NDWEQTA + OHLC, manual DWA export + Norgate) have effectively equivalent backtest capability — only path 2 additionally enables tuning weights against DWA's historical TA score, which is a marginal advantage since our production composite is what we're actually optimizing for. See [research/ndw-data-link-alternatives.md](research/ndw-data-link-alternatives.md#a0-existing-dwa-platform-subscription--daily-manual-csv-export--strong-v1-candidate) backtest implications note for detail.

---

## ~~OQ-008: DWA Technical Attributes score usage~~ — RESOLVED 2026-05-16

- **Resolution:** Yes — the advisor uses the Technical Attributes score and the full DWA toolset; the bot must include the same. See [decisions log 2026-05-16](01-decisions-log.md#2026-05-16--advisor-relies-on-dwa-technical-attributes-score-and-the-full-dwa-toolset-resolves-oq-008).
- **Implication:** Drives OQ-002 toward Option A (Nasdaq Data Link) — the Technical Attributes score is not replicable from raw OHLC.

---

## ~~OQ-009: Liquidity floor for the universe~~ — RESOLVED 2026-05-16

- **Resolution:** $1 minimum price floor, no explicit volume filter. See [decisions log 2026-05-16](01-decisions-log.md#2026-05-16--universe-liquidity-floor-1-minimum-price-no-explicit-volume-floor-resolves-oq-009).
- **Caveat to revisit:** if reports start surfacing low-volume names where execution costs would dominate position size, add a volume floor (e.g., min 20-day avg dollar volume $100K) later.
