# Research: Nasdaq Data Link NDW Database — Pricing & Coverage

**Researched:** 2026-05-16
**Trigger:** [OQ-002](../02-open-questions.md#oq-002-dwa-access-path--provisionally-resolved-2026-05-16-pending-pricing) was provisionally resolved toward Option A (license the Nasdaq Data Link NDW database) once the advisor confirmed they rely on the proprietary DWA Technical Attributes score (resolves [OQ-008](../02-open-questions.md#oq-008-dwa-technical-attributes-score-usage--resolved-2026-05-16)). This document captures the pricing and coverage details needed to finalize that commitment.

---

## 1. Pricing — public information is gated behind sales

**No public dollar figures exist for any of the three NDW databases** (NDWEQTA, NDWTA, NDWFUNDTA).

What was checked:
- Each database's product page on `data.nasdaq.com` — these are JavaScript-rendered single-page apps that do not expose pricing to crawlers or in static HTML
- Nasdaq's consolidated DWA pricing page (`nasdaq.com/solutions/pricing-for-nasdaq-dorsey-wright-investment-research-technical-analysis-platform`) — lists discount categories but no list prices
- Search across forums, advisor blogs, financial-data review sites

What the public Nasdaq pricing page *does* confirm: discount programs exist for:
- Volume programs (10+ advisors in one firm)
- Academic / CMT-credentialed users
- Advisors licensed for ≤10 years
- Retired advisors
- Non-professional users

### How to actually get pricing

Call Nasdaq Dorsey Wright sales directly:
- **Sales:** (212) 312-0333
- **Billing:** (804) 525-2270

When calling, request quotes for each SKU individually (NDWEQTA, NDWTA, NDWFUNDTA) and ask whether a single-advisor seat covers internal use in a screening tool.

### Reference order-of-magnitude

For comparison, other Nasdaq Data Link premium feeds in similar categories typically run:
- **~$50–$500/month per database** for individual subscriber tiers
- **~$1,500–$10,000+/year** for institutional tiers

The NDW databases may fall above this range given their advisor-grade content and the existing DWA platform subscription's pricing model. This range is informational only — get the actual quote from sales.

---

## 2. NDWEQTA coverage — what's confirmed, likely, and unconfirmed

The exact NDWEQTA schema is documented on a JavaScript-rendered page that did not return raw content to the research crawler. Coverage below is inferred by triangulating across the publisher description, Nasdaq's article on the Technical Attribute system, and the DWA P&F Basics PDF.

| Field | Status | Notes |
|---|---|---|
| **Daily P&F signal status** (current signal, type, last change date) | **Highly likely included** | This is the core DWA output and is what NDWEQTA exists to deliver. |
| **P&F trend posture** (above bullish support / below bearish resistance) | **Highly likely included** | One of the five inputs to the Technical Attributes score. |
| **Relative Strength data** (rankings vs. market, vs. sector/peer) | **Confirmed conceptually** | The TA score is built from "two vs. the market, two vs. the sector" RS comparisons — the underlying RS data must be present. |
| **Long-term RS buy/sell signal** | **Highly likely included** | Standard DWA equity field. |
| **Technical Attributes composite score (0–5)** | **Confirmed** | The headline DWA equity metric and the reason for licensing this database. |
| **DWA sector / group classifications** | **Likely included** | DWA's ~40 proprietary group taxonomy is standard metadata on equity records. |
| **Bullish Percent Index data** (universe + sector BPIs) | **Likely in NDWTA**, unclear if duplicated in NDWEQTA | Confirm with sales — if NDWEQTA carries BPI series, we don't need NDWTA. If not, NDWTA becomes a second required database. |
| **Raw P&F chart column data** (every X/O box, column highs/lows/dates) | **Unconfirmed — probably NOT included** | Data Link feeds are tabular by design; raw chart history is typically a platform-UI feature. If absent, the bot must construct charts from OHLC ourselves for visualization. The signals are still available from the API — we just lack the box-level chart data to render. |

**Bottom line on coverage:** NDWEQTA almost certainly includes everything the screener *decides* on (signals, RS, Technical Attributes score). It may or may not include everything the bot *displays* (the literal P&F chart for the report). The chart-rendering gap is fillable: we already plan to build a P&F engine from OHLC, and we use it just for rendering when needed.

---

## 3. Update frequency

Not stated publicly for the Data Link feeds. Inferred from how DWA's platform itself works:

- The underlying NDW Research Platform updates **daily, after US market close**.
- DWA's BigWire daily commentary is published each evening.
- The Data Link feed is therefore **almost certainly end-of-day daily**, with new data available overnight (typically several hours after the 4 PM ET close).

There is no published SLA on lag between platform update and API availability. **Confirm exact timing with sales** — for a daily report cadence, we need the new data to be available before our report run time.

---

## 4. License terms — relevant constraints

Nasdaq Data Link's premium databases follow an **à la carte per-database subscription model**, cancellable, with premium support and the highest API rate limits. General platform terms:

- **Internal use only** — data is licensed for the named subscriber's own use.
- **No redistribution** to third parties (clients, other firms, public publications).
- **Derivative works for internal screening tools** are typically permitted under the standard single-user premium license — that is exactly our use case.
- **Per-seat / per-user terms apply** — sharing API keys across advisors or adding additional users is a breach.
- **NDW datasets may carry a financial-advisor-grade addendum** requiring an institutional/professional license. This is something to confirm before purchase.

**Action item:** request the actual license PDF from sales and have the advisor's firm review it. If the firm has a compliance officer who reviews data vendor agreements, this is their domain.

---

## 5. Recommendation

For a single advisor running an internal daily screening bot whose decisive input is the Technical Attributes score:

1. **License NDWEQTA only.** It is the targeted equity P&F + Technical Attributes SKU and is the minimum sufficient feed.
2. **Skip NDWFUNDTA.** Funds are not in scope for this project (long US equities only).
3. **Decide on NDWTA after confirming BPI coverage in NDWEQTA.** If NDWEQTA carries BPI series for the universe and sectors, NDWTA is redundant. If not, NDWTA is needed for the BPI regime overlay.
4. **Plan to build P&F chart visualization ourselves from OHLC.** The Data Link feed gives signal-level fields; raw box-by-box chart history is likely platform-only. We need a separate OHLC vendor (Polygon.io, Tiingo, EODHD) for chart rendering anyway — same vendor we planned to use under the previous Option C path.
5. **Before purchasing**, place a call to (212) 312-0333 and ask for:
   - The NDWEQTA data dictionary / table list / sample CSV
   - Confirmation of whether BPI series are included in NDWEQTA
   - The single-advisor license PDF
   - A 30-day evaluation period if available
   - Pricing for NDWEQTA standalone, and for NDWEQTA + NDWTA bundled if BPI isn't in NDWEQTA

---

## 6. What "all DWA outputs" means in practice for this project

With Option A (Nasdaq Data Link) chosen, the bot's data architecture becomes:

```
Nasdaq Data Link NDWEQTA          Polygon.io / Tiingo / EODHD
─────────────────────             ───────────────────────
- Daily P&F signal status         - Daily OHLC for the full universe
- P&F trend posture               - Adjusted prices (splits, dividends)
- RS rankings + signals           - Historical bars for backtest
- Technical Attributes score      - SPXEWI or RSP proxy for RS validation
- DWA sector classifications        (optional, since DWA gives us RS)
- BPI data (if included)
- DWA-defined universe coverage

           ↓                                ↓
      ┌─────────────────────────────────────────┐
      │  Fundamental data vendor                │
      │  (Financial Modeling Prep or SimFin)    │
      │  - FCF, ROE, debt/equity, growth,       │
      │    valuation, earnings calendar         │
      └─────────────────────────────────────────┘
                       ↓
              Screening engine
                       ↓
             Daily report (PDF)
```

This is a more straightforward architecture than the previous Option C path. We avoid re-implementing DWA's signal logic and instead consume their authoritative outputs, while still owning the chart rendering and fundamental filter.

---

## Open items to resolve with Nasdaq sales

1. **Exact pricing** for NDWEQTA single-advisor seat
2. **BPI coverage** in NDWEQTA vs. needing NDWTA
3. **Update timing** SLA (when after market close is the data available)
4. **License terms** review — especially whether single-advisor / internal-screener use is explicitly permitted
5. **Trial / evaluation period** availability
6. **What's in the data dictionary** — schema, table list, field definitions

These should be answered before final commitment to Option A.

---

## Sources

- [NDWEQTA product page](https://data.nasdaq.com/databases/NDWEQTA)
- [NDWTA product page](https://data.nasdaq.com/databases/NDWTA)
- [NDWFUNDTA product page](https://data.nasdaq.com/databases/NDWFUNDTA)
- [NDW publisher page](https://data.nasdaq.com/publishers/NDW)
- [Nasdaq Dorsey Wright pricing page (no public dollar figures)](https://www.nasdaq.com/solutions/pricing-for-nasdaq-dorsey-wright-investment-research-technical-analysis-platform)
- [Nasdaq — Technical Attribute stock ranking system](https://www.nasdaq.com/articles/how-to-pick-em:-the-technical-attribute-stock-ranking-system)
- [DWA Point and Figure Basics PDF](https://www.nasdaq.com/docs/DWA-Point-Figure-Basics_0.pdf)
- [NDW Research Platform User Guide PDF](https://dorseywright.nasdaq.com/docs/NDW_Research_Platform_User_Guide.pdf)
- [Nasdaq Data Link premium data licensing help](https://help.data.nasdaq.com/category/517-licensing)
- [Nasdaq Data Link terms of service](https://data.nasdaq.com/terms)
