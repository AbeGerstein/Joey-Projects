# Research: Dorsey Wright Data Access Mechanics

**Researched:** 2026-05-15
**Researcher:** Claude (general-purpose research agent), sources cited inline and at the end

This document captures the full findings of the investigation into how a financial advisor with a Dorsey Wright / Nasdaq Dorsey Wright (NDW) subscription can programmatically access their data for an internal screening tool, and what restrictions apply. The conclusion drives [decision OQ-002](../02-open-questions.md#oq-002-dwa-access-path) in the open-questions log.

---

## 1. Official programmatic channel: Nasdaq Data Link

Nasdaq Dorsey Wright publishes their data through **Nasdaq Data Link** (formerly known as Quandl) via REST API. Three distinct premium databases exist under NDW's publisher account:

| Database code | Contents |
|---|---|
| **NDWEQTA** | Equity Technical Analysis Data — per-security P&F signals, RS rankings, technical attributes for individual stocks |
| **NDWFUNDTA** | Fund Technical Analysis Data — the same fields for mutual funds and ETFs |
| **NDWTA** | Technical Analysis Data — a broader composite database |

These contain Dorsey Wright's proprietary outputs: P&F signal status, signal change dates, RS rankings, the "Technical Attributes" composite score, sector rotations, etc.

**Critical:** these are **separately licensed premium data feeds**. A standard NDW Research Platform subscription (the web UI at dorseywright.nasdaq.com) does **not** automatically include API entitlement. To use the API you must subscribe to each Data Link database separately and pay for it. Exact pricing tiers are gated behind sales — Nasdaq's published pricing page indicates volume discounts for advisor groups, reduced rates for advisors licensed under 10 years, and non-professional rates, but specific dollar figures require a sales quote.

**Contact for licensing:**
- Sales: (212) 312-0333
- Technical: (804) 320-8511

There is some mention in public Schwab Advisor Services materials of an "OpenView Gateway" integration that pipes NDW data to Schwab-platform advisors, but that is a Schwab-specific channel — not a general developer API.

---

## 2. Terms of Service — scraping is explicitly prohibited

NDW's Terms of Use, published at `https://www.nasdaq.com/docs/NDW-Terms-of-Use-Disclosures.pdf` and `https://dorseywright.nasdaq.com/help/disclosures/`, explicitly forbid automated extraction from `nasdaqdorseywright.com` and `systems.dorseywright.com`.

Representative language from the Terms of Use:

> Users may "not access or use the Service, or any process, whether automated or manual, to capture data or content from the Service or circumvent any mechanisms for preventing the unauthorized reproduction or distribution of the Service."

Additional relevant clauses:
- Scraping, data mining, and automated capture for AI/ML training are forbidden without express written permission.
- The license granted to subscribers is "personal, limited, revocable, non-exclusive, non-assignable, non-sublicensable, non-transferable" for internal advisory use.
- Derivative works and redistribution require prior written approval.
- Governing law: New York.

**Implication:** scraping the DWA web platform is a contractual breach **even for internal-only use**, regardless of redistribution intent. This option is off the table — both legally and as a risk to the advisor's firm.

---

## 3. Legitimate manual exports from the platform

The NDW Research Platform UI supports CSV/Excel exports for several views:
- **My Portfolios** — watchlist exports
- **Screener** — custom screen results
- **Relative Strength Matrix** — RS rankings across a universe

This was confirmed via NDW's user guide PDF (download timed out during the research; full enumeration of exportable views requires platform login) and Zendesk support articles.

A subscriber feeding these CSVs into a downstream internal tool is **consumption, not automated capture** — that path is legitimate under the Terms of Use.

**Unclear without platform login:**
- Whether exports include all fields the advisor sees on screen (e.g., DWA Technical Attributes composite score, sector BPI history, signal timestamps) or are limited to a display-column subset.
- Whether export volumes are rate-limited.

This is something the advisor can quickly test in their existing platform session.

---

## 4. Third-party platforms that license DWA data

| Platform | Has DWA data? | Notes |
|---|---|---|
| **Nasdaq Data Link** | Yes (primary channel) | Separately licensed; see section 1 |
| **Schwab Advisor Services / OpenView Gateway** | Yes (Schwab-platform advisors only) | Redistributes a subset to Schwab-platform advisors |
| **Optuma** | No — independently computed | Computes its own P&F charts, RS ratio charts, and BPI from raw price data. These are *not* "DWA RS Rating"; they're Optuma's own implementations |
| **Bloomberg** | No native DWA indicators | Surfaces DWA-managed funds and indexes (DWA* tickers) but does not expose DWA's per-security signal database |
| **FactSet** | No native DWA indicators | Same as Bloomberg |
| **eSignal** | No | No evidence of DWA licensing |
| **TradingView, StockCharts, etc.** | No | All compute P&F independently |

---

## 5. Replication path — building from raw OHLC

The core DWA methodology is publicly documented enough to replicate faithfully. The key pieces:

### Point and Figure chart construction
Pure math. Given OHLC and a box-scaling rule, the chart is deterministic. See [../methodology/point-and-figure.md](../methodology/point-and-figure.md) for the algorithm.

### Relative Strength
DWA's RS methodology is published in their support documentation:

> Divide security price by **S&P 500 Equal Weighted Index (SPXEWI)**, multiply by 100. Plot the resulting ratio as a P&F chart with **6.5% box size for stocks**, **3.25% for funds**, and a 3-box reversal. A long-term RS buy signal fires when a column of X's exceeds the prior column of X's; a sell signal fires when a column of O's drops below the prior column of O's.

Source: <https://nasdaqdorseywright.zendesk.com/hc/en-us/articles/15938757529869-Relative-Strength-Basics>

### Bullish Percent Index
The percentage of stocks in a defined universe currently on a P&F buy signal. Calculate by aggregating signal status across the universe.

### What we *cannot* replicate
- DWA's **proprietary "Technical Attributes" composite score** — not publicly documented.
- DWA's **exact universe definitions** for sector indexes — we'd need to construct our own sectors (e.g., using GICS classifications) which may not match DWA's groupings perfectly.

### Data inputs needed
Clean OHLC for the chosen universe over a multi-year history. Suitable vendors evaluated in [../data-sources.md](../data-sources.md):
- Polygon.io
- Tiingo
- EOD Historical Data
- Norgate

Plus index data for SPXEWI (the Equal Weighted S&P 500) — available from any of the above.

---

## Recommendation

**For v1, go with replication from raw OHLC (option C in [OQ-002](../02-open-questions.md#oq-002-dwa-access-path)).** Reasoning:

1. **No DWA licensing friction.** The Data Link database licensing path requires a sales quote and incremental cost on top of the platform subscription the advisor already pays for. v1 should prove the bot's value before adding that line item.
2. **Full control and inspectability.** Replicating the methodology means we own every step of the signal generation. The advisor can ask "why was this name flagged?" and get a complete answer, not a black-box score from a third party.
3. **No legal ambiguity.** No risk around redistribution or ToS interpretation.
4. **The DWA platform stays usable as a cross-check.** The advisor still has their NDW subscription; they can spot-check the bot's outputs against the platform's own charts whenever they want.

**v2 consideration:** if the advisor confirms they rely on DWA's "Technical Attributes" composite score in their actual workflow (see [OQ-008](../02-open-questions.md#oq-008-does-the-advisor-use-dwas-technical-attributes-composite-score)), licensing the NDW Data Link database in v2 becomes much more attractive — it's the only way to get that score.

---

## Open caveats flagged by research

1. **Exact Data Link pricing** is not public; requires a sales quote.
2. **Full export field list** on the Research Platform is visible only after login — the advisor should spot-check whether the available exports cover everything they'd want to use.
3. **Existence of a private/institutional NDW REST API outside Data Link** could not be confirmed from public sources. There may be enterprise-only channels not surfaced publicly.

---

## Sources

- [Nasdaq Data Link — NDW publisher page](https://data.nasdaq.com/publishers/NDW)
- [NDW Equity Technical Analysis database](https://data.nasdaq.com/databases/NDWEQTA)
- [NDW Technical Analysis database](https://data.nasdaq.com/databases/NDWTA)
- [NDW Fund Technical Analysis database](https://data.nasdaq.com/databases/NDWFUNDTA)
- [NDW Terms of Use & Disclosures PDF](https://www.nasdaq.com/docs/NDW-Terms-of-Use-Disclosures.pdf)
- [DWA Help — Disclosures](https://dorseywright.nasdaq.com/help/disclosures/)
- [NDW pricing overview](https://www.nasdaq.com/solutions/pricing-for-nasdaq-dorsey-wright-investment-research-technical-analysis-platform)
- [DWA Relative Strength methodology](https://nasdaqdorseywright.zendesk.com/hc/en-us/articles/15938757529869-Relative-Strength-Basics)
- [DWA RS Matrix basics](https://nasdaqdorseywright.zendesk.com/hc/en-us/articles/19226088223373-Relative-Strength-Matrix-Basics)
- [Nitrogen Wealth — P&F + RS Signals whitepaper](https://nitrogenwealth.com/wp-content/uploads/2022/12/Pnf_RS_Signals_Whitepaper.pdf)
- [Schwab Advisor Services — NDW Research Platform integration](https://advisorservices.schwab.com/provider-solutions/Nasdaq-Dorsey-Wright-Research-Platform)
- [Optuma — Point and Figure chart documentation](https://www.optuma.com/kb/optuma/charts/point-and-figure-chart)
- [Nasdaq Data Link help — troubleshooting](https://help.data.nasdaq.com/article/497-the-api-is-not-working-for-me-what-should-i-do)
