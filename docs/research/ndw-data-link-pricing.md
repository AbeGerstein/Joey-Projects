# Research: Nasdaq Data Link NDW Database — Pricing & Coverage

**Researched:** 2026-05-16 (initial)
**Updated:** 2026-05-16 (hardened with direct API metadata queries)
**Trigger:** [OQ-002](../02-open-questions.md#oq-002-dwa-access-path--provisionally-resolved-2026-05-16-pending-pricing) — locking in the DWA access path now that [OQ-008](../02-open-questions.md#oq-008-dwa-technical-attributes-score-usage--resolved-2026-05-16) confirmed the advisor needs the Technical Attributes score.

---

## 1. Pricing — public information is gated behind sales

**No public dollar figures exist for any of the NDW databases.**

What was checked:
- Each database's product page on `data.nasdaq.com` — JavaScript-rendered SPAs that do not expose pricing to crawlers
- Nasdaq's consolidated DWA pricing page — lists discount categories only
- Search across forums, advisor blogs, financial-data review sites — no current dollar figures

The public Nasdaq pricing page confirms discount programs for: volume programs (10+ advisors), academic / CMT-credentialed users, advisors licensed for ≤10 years, retired advisors, and non-professional users.

### How to actually get pricing

Call Nasdaq Dorsey Wright sales directly:
- **Sales:** (212) 312-0333
- **Billing:** (804) 525-2270

When calling, request quotes specifically for **NDWEQTA** (see §2 below — this is the only equity database that actually exists as a queryable datatable). Ask whether a single-advisor seat covers internal use in a screening tool.

### Reference order-of-magnitude

For comparison, other Nasdaq Data Link premium feeds in similar categories typically run:
- **~$50–$500/month** per database for individual subscriber tiers
- **~$1,500–$10,000+/year** for institutional tiers

NDW may fall above this range given its advisor-grade content. Get the actual quote from sales — this range is for orientation only.

---

## 2. What actually exists on Nasdaq Data Link (HARDENED)

The previous version of this document inferred coverage from marketing materials. The updated investigation queried Nasdaq Data Link's **API metadata endpoints directly** to confirm what exists. Findings:

### Only two NDW datatables exist as real, queryable resources

The metadata endpoint `https://data.nasdaq.com/api/v3/datatables/{vendor}/{code}/metadata.json` returns valid responses for exactly two NDW codes:

| Datatable | Status | Update frequency | Primary key | Filters available |
|---|---|---|---|---|
| **NDW/EQTA** — Equity Technical Analysis Data | **Exists** | CONTINUOUS | `(id_stock, date)` | bambu, country, date, exchange_code, import_region, symbol |
| **NDW/FUNDTA** — Fund Technical Analysis Data | **Exists** | CONTINUOUS | `(id_stock, date)` | country, date, exchange_code, import_region, symbol |
| **NDW/TA** — "Technical Analysis Data" (broader) | **Does NOT exist** | — | — | — |

**Important correction from the initial research:** the previously-mentioned "NDWTA" database does not resolve as a real datatable. It appears in some marketing pages and old listings but the actual datatable code returns 404. The publisher catalog has been consolidated to NDWEQTA + NDWFUNDTA only.

### Column-level schema is still gated

Both metadata responses return `columns: []` — the column list itself is hidden behind a paid subscription. The exact field names and types can be obtained only by:
- Licensing the database
- Getting a sales-rep data dictionary PDF
- Running one authenticated API call against the data endpoint with a valid API key

### Per-field coverage findings

| # | Field | Finding | Evidence |
|---|---|---|---|
| 1 | Daily P&F signal status (DT/DB/TT/TB/catapult, last change date) | **Confirmed present** | Core DWA output; BigWire references column status; metadata key `(id_stock, date)` shape supports per-day signal snapshots |
| 2 | P&F trend posture (above bullish support / below bearish resistance) | **Confirmed present** | DWA's published "5-for-5'er" rating requires this; it's one of the 5 Technical Attribute inputs |
| 3 | Relative Strength rankings (vs market, vs sector) | **Confirmed present** | Multiple RS variables explicit in the NDW Fund Score whitepaper; BigWire shows market and peer RS signals |
| 4 | Long-term RS buy/sell signals | **Confirmed present** | Listed as a scoring input in the Fund Score whitepaper |
| 5 | **Technical Attributes composite score (0–5)** | **Confirmed present** | The headline DWA equity metric — the reason for licensing this database |
| 6 | DWA sector / group classifications | **Unclear** | Filters expose `country`, `exchange_code`, `import_region` but **not** `sector`. DWA's proprietary DALI sector data appears in a *separate* feed (the FRED `NASDAQNQDALIDE` series), suggesting it may not be a column inside NDWEQTA. May need to derive sector tags from a separate source (GICS via the fundamentals vendor). |
| 7 | **Bullish Percent Index series** (universe + sector BPIs) | **Confirmed ABSENT** | BPI is a universe-level aggregate; NDWEQTA's primary key is `(id_stock, date)` which is per-security and structurally cannot hold universe aggregates. **No Nasdaq Data Link datatable exists for BPI** — it appears to be platform-only on dorseywright.nasdaq.com. |
| 8 | **Raw P&F chart column data** (every X/O box, column highs/lows/dates) | **Confirmed ABSENT** | Would require per-column rows, which the `(id_stock, date)` primary key precludes. No `*CHART*`, `*COL*`, or `*BOX*` sibling datatable exists. Chart visuals are platform-only. |

---

## 3. What we can build ourselves (filling the gaps)

Two of the absent fields above (BPI and raw chart data) are things we already planned to build in the Phase 2 P&F engine. The absence is not a blocker.

### Bullish Percent Index — fully self-buildable

BPI is defined as `(count of stocks on a P&F buy signal / total stocks in universe) × 100`. Once NDWEQTA gives us each stock's current signal status, BPI is a one-line aggregation. The plotting of BPI as a P&F chart (with 2% boxes, 3-box reversal) is the same chart-construction code we're already writing.

Sector BPIs are computed the same way, using sector subsets of the universe. We just need sector tags — which we'd derive from either (a) NDWEQTA if it does include them after all, (b) our fundamentals vendor's GICS tags, or (c) the FRED NASDAQNQDALIDE series for DWA's own DALI sectors.

**Implication:** building BPI ourselves is straightforward, but it requires we **trust the signal column from NDWEQTA**. If we wanted full independence we could detect signals from raw OHLC ourselves — and in fact we'll build that engine anyway for chart visualization. That gives us an automatic cross-check: our self-detected signals should agree with DWA's signals. Disagreements are bugs in our P&F engine, which we'd investigate and fix.

### Raw P&F chart visualization — fully self-buildable

This was always the plan ([methodology/point-and-figure.md](../methodology/point-and-figure.md)). Given OHLC data, the P&F chart is deterministic under Dorsey's box-scaling and 3-box-reversal rules. The chart is needed for the report so the advisor can visually inspect each candidate. The fact that NDWEQTA only carries signal-level data, not box-level data, doesn't change our architecture.

**Cross-validation opportunity:** since we're building the chart ourselves *and* getting DWA's signals from the API, every report will implicitly check that our chart's most recent signal matches DWA's. This is free unit testing for our P&F engine and gives the advisor confidence the bot is faithful to DWA conventions.

### Sector classifications

If NDWEQTA doesn't include DWA's proprietary sector tags, we have three options:
1. Use **GICS sectors** from our fundamentals vendor (Financial Modeling Prep, SimFin, etc.). The 11 GICS sectors are the industry standard and align reasonably with DWA's groupings at the sector level (though not at DWA's more granular ~40-group level).
2. License the **FRED NASDAQNQDALIDE series** if it carries the per-stock DALI sector assignments (free from FRED).
3. **Ask sales** when calling about NDWEQTA whether sector tags are included as a column.

GICS is the safest default. Sector-level BPIs computed with GICS will be slightly different from DWA's, but they'll be directionally correct and well-defined.

---

## 4. Update frequency

Confirmed: NDWEQTA's `update_frequency` field returns `"CONTINUOUS"` in the metadata endpoint. In practice this almost certainly means **daily after US market close** — DWA's underlying platform updates daily and BigWire posts each evening. The "CONTINUOUS" label is a Data Link enumeration value and doesn't imply intraday updates.

Exact timing (e.g., "available by 6pm ET") is not published. Confirm with sales when ordering — we need the new data available before our daily-report run time.

---

## 5. License terms — relevant constraints

Nasdaq Data Link's premium databases follow an **à la carte per-database subscription model**, cancellable, with premium support and the highest API rate limits.

- **Internal use only** — licensed to the named subscriber.
- **No redistribution** to third parties.
- **Derivative works for internal screening tools** are typically permitted under the standard single-user premium license — our use case.
- **Per-seat / per-user terms apply** — sharing API keys across advisors is a breach.
- **NDW datasets may carry a financial-advisor-grade addendum** requiring an institutional/professional license. Confirm before purchase.

**Action item:** request the actual license PDF from sales and confirm single-advisor internal-screener use is explicitly permitted.

---

## 6. Final recommendation

For this project:

1. **License NDWEQTA only.** It is the only equity database that actually exists. Skip any consideration of "NDWTA" or "NDWFUNDTA" (the former does not exist; the latter is funds, out of scope).
2. **Pull OHLC from Polygon.io (or Tiingo / EODHD)** for chart rendering and for self-computing P&F signals as a cross-check.
3. **Build BPI ourselves** from NDWEQTA's per-stock signal column. Sector BPIs use GICS sectors from the fundamentals vendor.
4. **Build chart visualization ourselves** for the daily report — Dorsey's deterministic P&F construction from OHLC, validated against NDWEQTA signals.
5. **Pull fundamentals from Financial Modeling Prep (or SimFin)** for the initial fundamental gate and for GICS sector tags.

This is essentially the same data architecture as the previously-considered Option C, but with NDWEQTA layered on top as the authoritative source for DWA's proprietary outputs (Technical Attributes score, RS rankings, official signals). It is the best of both worlds: we get DWA's value-add without giving up control of the rest of the stack.

### Cost summary (working)

| Item | Monthly cost (estimate) |
|---|---|
| Nasdaq Data Link NDWEQTA | **TBD — sales quote required**; estimate $50–$500/month based on comparable feeds |
| Polygon.io Stocks Starter | ~$29 |
| Financial Modeling Prep Starter | ~$25 |
| VM hosting + backups | ~$10 |
| **Total (with NDWEQTA at midpoint $200)** | **~$264/month** |

### Pre-purchase checklist to run with Nasdaq sales

When the advisor (or someone they delegate) calls (212) 312-0333:

1. **Pricing** for NDWEQTA single-advisor seat
2. **Data dictionary / sample CSV** — exact column names and types
3. **Sector classification fields** — confirm whether DWA sector/group tags are in NDWEQTA or require a separate feed
4. **Update timing SLA** — when after the 4 PM ET close is new data available
5. **License terms** — single-advisor internal-screener use explicitly covered? Per-seat constraints?
6. **Trial / evaluation period** availability
7. **Whether the advisor's existing NDW platform subscription bundles or discounts the API license**

---

## Sources

- [Nasdaq DWA NDWEQTA database page](https://data.nasdaq.com/databases/NDWEQTA)
- [Nasdaq DWA NDWFUNDTA database page](https://data.nasdaq.com/databases/NDWFUNDTA)
- [NDW publisher page](https://data.nasdaq.com/publishers/NDW)
- API metadata endpoint: `https://data.nasdaq.com/api/v3/datatables/NDW/EQTA/metadata.json` (returns name, primary_key, filters; columns gated)
- API metadata endpoint: `https://data.nasdaq.com/api/v3/datatables/NDW/FUNDTA/metadata.json` (same)
- [Nasdaq DWA pricing page (no public dollar figures)](https://www.nasdaq.com/solutions/pricing-for-nasdaq-dorsey-wright-investment-research-technical-analysis-platform)
- [DWA BigWire daily research](https://dorseywright.nasdaq.com/research/bigwire)
- [NDW Fund Score Whitepaper PDF](https://static.fmgsuite.com/media/documents/9ce3ed8a-3e1a-48ef-b236-faaf5876fce0.pdf) (extracted methodology; useful for inferring NDWEQTA's RS/signal field inventory)
- [Nasdaq Data Link in-depth usage docs](https://docs.data.nasdaq.com/docs/in-depth-usage-1)
- [Nasdaq Data Link terms of service](https://data.nasdaq.com/terms)
- [FRED Dorsey Wright DALI sector series (NASDAQNQDALIDE)](https://fred.stlouisfed.org/data/NASDAQNQDALIDE) — possible alternative source for DWA sector classifications
