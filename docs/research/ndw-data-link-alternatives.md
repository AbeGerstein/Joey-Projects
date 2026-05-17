# Research: Alternatives to Nasdaq Data Link NDWEQTA — Comprehensive

**Triggered:** 2026-05-16, after the advisor's pivot to (a) pure P&F screening with no fundamental filter, (b) pre-momentum detection as the explicit predictive intent, and (c) a two-section report including in-momentum names. All three pivots changed the cost calculus on NDWEQTA — see *Why this matters now* below.

This document evaluates alternatives to licensing the Nasdaq Data Link NDWEQTA database in case the sales quote (currently pending the callback from Nasdaq on 2026-05-16) comes in at a price tier that doesn't justify the spend.

> **Critical compliance note up front:** This is an automated screener built for a financial advisor's *commercial* use. Several otherwise-attractive vendors restrict their cheaper tiers to **personal / non-commercial** use only. Those tiers cannot be used here — automated commercial use would breach the ToS regardless of how small the operation is. Every option below has its commercial-use posture explicitly flagged.

### A clarification: "professional" classification is about who the subscriber is, not about whether the output is shared

A common misconception: that a tool whose output stays entirely on the advisor's computer (no clients see it, no distribution) qualifies for a vendor's "personal" or "non-commercial" tier. **This is not how data vendor terms work.**

The professional / non-professional classification is defined by the **subscriber's status**, not by the use case for any particular output:

- **Professional Subscriber** = anyone who is registered with the SEC/FINRA/state regulators, employed in the securities industry, or compensated for activities involving securities analysis or management
- **Non-Professional Subscriber** = effectively a retail investor managing only their own money outside the securities industry

This is the same classification framework the SEC and the exchanges (NYSE, NASDAQ) use for market data fees. It is consistent across the industry.

**Implication for this project:** a registered financial advisor is a Professional Subscriber by default — regardless of whether the bot's reports get shared with anyone. This means:

- Polygon's $29/mo Stocks Starter cannot be used — Polygon individual ToS forbids commercial use, and the advisor's professional status places him in the commercial category.
- Tiingo Power ($30/mo) cannot be used — that tier is explicitly individual-use-only.
- Any vendor whose pricing distinguishes "non-professional" from "professional" requires the professional tier.

**However,** several vendors don't penalize professional status at all in their entry pricing. Those are the vendors that fit this project:

- Marketstack Basic ($9.99/mo) permits commercial use at that price
- Norgate Data Platinum ($53/mo) accommodates professional advisor use at the listed price
- Alpaca Algo Trader Plus ($99/mo) includes a commercial license
- EODHD Commercial Internal-Use ($399/mo) is explicitly priced for this use case
- AmiBroker (one-time $299) permits professional use

**Action to take:** when subscribing to any vendor under serious consideration, answer their professional-status question truthfully. The vendors above will accept the advisor at the listed price. Trying to claim non-professional status at a vendor that would re-classify the advisor as professional is a ToS violation that can result in account termination plus retroactive billing at the professional rate. The audit-trail exposure is not worth the savings versus the vendors above.

---

## Why this matters now

When NDWEQTA was first proposed as the data source ([decisions log 2026-05-16](../01-decisions-log.md#2026-05-16--dwa-access-path-nasdaq-data-link-ndw-database-provisional-pending-pricing-partial-oq-002)), it was the obvious choice because the advisor relied on DWA's proprietary **Technical Attributes (TA) composite score**, which only NDWEQTA can deliver programmatically.

Three subsequent decisions have changed that calculus:

1. **The fundamental filter was removed entirely** — the bot is now pure P&F, removing the FMP / SimFin dependency from the stack.

2. **The predictive intent is now explicitly pre-momentum** — the TA score is designed for the opposite question (identifying stocks already strong). It is still useful in Section B (in-momentum) of the daily report, but it is no longer the prize input.

3. **The report has two sections, including stocks already in momentum.** The advisor wants both pre-momentum candidates (Section A) and in-momentum candidates (Section B) — so the value of the TA score is partially restored as a Section B input.

Net effect: NDWEQTA is **useful but not essential**. The bot can be built end-to-end without it.

### Revised cost-justification thresholds for NDWEQTA (when the quote arrives)

| NDWEQTA monthly | Recommendation |
|---|---|
| < $100 | License it — cheap insurance, advisor familiarity, signal cross-check, Section B input |
| $100–$300 | Marginal — license if the advisor wants the convenience of authoritative DWA signals |
| $300–$700 | Lean against — replicate from OHLC, fund the savings into a Section B-quality data source |
| > $700 | Skip — replicate from OHLC, use the advisor's existing platform manually for spot-checks |

These thresholds are working judgments. The advisor should review them.

---

## The alternatives, by tier

The vendors below are organized by category and ordered roughly by fit for this project (best fit first within each category).

### A. OHLC data vendors (for the build-it-ourselves path)

Pure price data. Combined with our own P&F engine, this gives us everything except DWA's proprietary TA score.

#### A1. EOD Historical Data (EODHD) — **strongest fit for compliance**

| Aspect | Detail |
|---|---|
| **Cost** | Personal tiers €19.99–€99.99/mo. **Commercial Internal-Use plan: $399/mo.** Enterprise $2,499/mo. |
| **Commercial use** | Explicit — the $399 Commercial Internal-Use plan is exactly the use case here |
| **Coverage** | Full US equities + 60+ global exchanges; 30+ years history |
| **API** | REST, well documented; intraday available on higher tiers |
| **Pros** | Clean commercial license at a defined price; no ambiguity |
| **Cons** | $399/mo is steeper than the personal-use OHLC vendors below |
| **Fit** | Excellent if compliance posture matters and a defined commercial license is preferred |
| **URL** | <https://eodhd.com/commercial-pricing> |

#### A2. Norgate Data — **strongest fit for backtest fidelity**

| Aspect | Detail |
|---|---|
| **Cost** | US Stocks Platinum **$630/yr (~$53/mo)** or $346.50/6mo |
| **Commercial use** | Subscription license permits internal use by a single subscriber including advisor work |
| **Coverage** | Full US equities + delisted names + **historical index constituents back to 1990** — survivorship-bias-free |
| **API** | Desktop application with Python bindings (NorgateData package on PyPI) |
| **Pros** | Best-in-class historical data quality; clean point-in-time backtesting; reasonable price |
| **Cons** | Not pure-REST; requires their desktop install on the host. Slightly less ergonomic than a cloud API. |
| **Fit** | Excellent for Phase 4 backtest fidelity; could be the *primary* OHLC source given price |
| **URL** | <https://norgatedata.com/prices.php> |

#### A3. Marketstack — **cheapest viable option**

| Aspect | Detail |
|---|---|
| **Cost** | Free 100 req/mo (too limited); **Basic $9.99/mo** (10K req, 10yr history, commercial use permitted); Professional $49.99/mo (100K req, real-time); Business $149.99/mo |
| **Commercial use** | Basic tier and above explicitly permit commercial use |
| **Coverage** | Full US equities + global |
| **API** | REST |
| **Pros** | Genuinely cheap with explicit commercial license; lots of headroom for our scale |
| **Cons** | Less battle-tested in advisor / fintech communities; data quality reviews are mixed |
| **Fit** | Strong cost-driven choice; verify data quality on a sample before committing |
| **URL** | <https://marketstack.com/pricing> |

#### A4. Alpaca Markets — **best broker-bundled option**

| Aspect | Detail |
|---|---|
| **Cost** | Free tier IEX-only (15-min delayed); **Algo Trader Plus $99/mo** (full SIP, unlimited symbols, 7+ years history) |
| **Commercial use** | Algo Trader Plus permits commercial use |
| **Coverage** | Full US equities, real-time on paid tier |
| **API** | REST + WebSocket; very developer-friendly |
| **Pros** | Clean modern API; full SIP data; commercial license; the same Alpaca account could host trade execution if that's ever in scope (it isn't currently — bot does not place trades) |
| **Cons** | None significant for our use case |
| **Fit** | Strong; one of the easiest API integrations available |
| **URL** | <https://alpaca.markets/data> |

#### A5. Tiingo — *only with Commercial plan*

| Aspect | Detail |
|---|---|
| **Cost** | Free (limited); Power ~$30/mo (individual use only); **Commercial = sales quote** |
| **Commercial use** | **Power tier is individual-use only** — cannot be used for an advisor's commercial screener. Need the Commercial plan, pricing not public. |
| **Coverage** | Full US equities + fundamentals; 30+ year history |
| **API** | REST, well documented |
| **Pros** | Strong adjustment quality and developer reputation |
| **Cons** | Commercial tier requires sales quote; pricing unknown |
| **Fit** | Worth a quote, but expect higher pricing than personal-tier |
| **URL** | <https://www.tiingo.com/about/pricing> |

#### A6. Polygon.io — **WARNING: individual tier prohibits commercial use**

| Aspect | Detail |
|---|---|
| **Cost** | Stocks Starter $29/mo, Developer $79/mo, Advanced $199/mo |
| **Commercial use** | **Individual ToS forbids commercial use.** Commercial use requires the Business ToS (sales quote). |
| **Coverage** | Full US equities; up to 20+ years history on higher tiers |
| **API** | Modern REST, generous rate limits |
| **Pros** | Great developer experience, strong data quality |
| **Cons** | **Cannot be used at retail tier for our screener.** Earlier project docs assumed Starter would work — that was incorrect. Need to use Polygon's Business tier or substitute. |
| **Fit** | Available only via Business tier — get a sales quote if interested |
| **URL** | <https://polygon.io/legal/Commercial_Use_Terms.pdf> |

#### A7. Alpha Vantage — workable but limited

| Aspect | Detail |
|---|---|
| **Cost** | Free 25 req/day; Premium $49.99 (75 rpm), $99.99 (150 rpm), $149.99 (300 rpm), $249.99 (1,200 rpm + SLA) |
| **Commercial use** | Premium tiers permit internal commercial use |
| **Coverage** | US + global equities; sufficient history |
| **API** | REST; well known but feels dated |
| **Pros** | Reasonable cost; commercial use OK on paid tiers |
| **Cons** | Rate limits are tight for a 6,000-name daily refresh — would need the $149.99 tier minimum |
| **Fit** | Acceptable fallback; not a first choice |
| **URL** | <https://www.alphavantage.co/premium/> |

#### A8. Finnhub

| Aspect | Detail |
|---|---|
| **Cost** | Free 60 calls/min (US only); paid plans ~$50/mo Starter to ~$100/mo Standard with modular add-ons |
| **Commercial use** | Permitted on paid plans |
| **Coverage** | Full US equities |
| **API** | REST |
| **Pros** | Modular pricing; decent coverage |
| **Cons** | The à la carte add-on model can get complex quickly |
| **Fit** | Workable; less straightforward than EODHD or Alpaca for our use |
| **URL** | <https://finnhub.io/pricing> |

#### A9. Twelve Data

| Aspect | Detail |
|---|---|
| **Cost** | Individual Pro $79–$99/mo (credit-based); Business Basic free → Grow $79 → Pro $249 → Ultra $499 → Enterprise $1,099+ |
| **Commercial use** | Commercial display rights require Business tier (Grow $79/mo minimum for commercial) |
| **Coverage** | Full US equities + global |
| **API** | REST; well documented |
| **Pros** | Modern API, well-tiered |
| **Cons** | Credit-based metering can be hard to predict cost on |
| **URL** | <https://twelvedata.com/pricing> |

#### A10. Intrinio

| Aspect | Detail |
|---|---|
| **Cost** | Product-based: EOD US Prices ~$3,100/yr; IEX RT $6,000/yr; SIP 15-min $6,000/yr |
| **Commercial use** | Yes |
| **Coverage** | Strong; product-based packaging |
| **Pros** | Reliable, institutional-grade data |
| **Cons** | Higher cost, sales-quoted bundles |
| **Fit** | Better fit for established firms than a starter project |
| **URL** | <https://intrinio.com/pricing> |

---

### B. Broker-provided market data + APIs

These come bundled with a brokerage account and can be very cost-effective.

#### B1. Schwab Trader API (formerly TD Ameritrade)

| Aspect | Detail |
|---|---|
| **Cost** | Free with a Schwab brokerage account |
| **Commercial use** | Personal trading; advisor commercial use is gray area — confirm with Schwab Advisor Services |
| **Status** | TD Ameritrade API was **shut down May 2024**; replaced by Schwab Trader API at developer.schwab.com. Approval required. |
| **Coverage** | Full US equities with delayed quotes by default; real-time requires data subscription |
| **API** | REST; OAuth flow |
| **Pros** | Free; could integrate with the advisor's existing Schwab platform (if they're a Schwab advisor) |
| **Cons** | Approval process; commercial use case for advisor's screener needs to be vetted with Schwab; the existing thinkorswim platform itself has no public API |
| **Fit** | Worth investigating *only if* the advisor's firm clears it with Schwab Advisor Services |
| **URL** | <https://developer.schwab.com/> |

#### B2. Interactive Brokers (IBKR) — TWS / Client Portal API

| Aspect | Detail |
|---|---|
| **Cost** | API free; market data subscriptions cost extra. Non-pro: free Cboe One + IEX bundle covers all US listed; full SIP $4.50–$15/mo per bundle. **Professional rate (advisor = professional) is ~10× the non-pro rate** unless reclassified. |
| **Commercial use** | OK with an IBKR account; advisor-grade data subscriptions apply |
| **Coverage** | Full US equities |
| **API** | TWS API (long-established) or newer Client Portal API |
| **Pros** | Cheap data; mature platform |
| **Cons** | Advisor classification triples data costs; TWS API is technically clunky |
| **URL** | <https://www.interactivebrokers.com/en/pricing/market-data-pricing.php> |

---

### C. Charting / analysis platforms with native P&F

These are alternatives to building the P&F engine ourselves. They come with P&F primitives built in but trade some customization for it.

#### C1. Optuma

| Aspect | Detail |
|---|---|
| **Cost** | Trader Edition $75/mo or $810/yr; **Professional $125/mo or $1,350/yr** (includes OSL scripting) |
| **Commercial use** | Permitted |
| **P&F support** | Native; methodologically faithful to traditional 3-box conventions |
| **API** | No external REST API. OSL (Optuma Scripting Language) runs in-app; can produce screen outputs, but the workflow is platform-centric rather than service-oriented |
| **Pros** | Saves building the P&F engine ourselves; mature platform; comprehensive technicals |
| **Cons** | Lock-in to their platform; less customization for our pre-momentum / in-momentum specific logic; the platform-centric model fights our daily-cron architecture |
| **Fit** | Not a great fit because the daily-bot architecture needs a service, not a desktop app. Considered for completeness. |
| **URL** | <https://portal.optuma.com/store/optuma-professional-services-subscription/> |

#### C2. AmiBroker — **interesting low-cost long-term play**

| Aspect | Detail |
|---|---|
| **Cost** | Standard $279–$299 **one-time** (with 24 months of free updates); Professional $339–$379 one-time; Ultimate Pack Pro $497 one-time |
| **Data feed** | Separate ($20–$50/mo via Norgate or IQFeed) |
| **Commercial use** | One-time license; commercial advisor use is allowed |
| **P&F support** | Built-in, fully scriptable via AFL (AmiBroker Formula Language) |
| **API** | AFL scripts + COM/OLE automation |
| **Pros** | Very low ongoing cost; combined with Norgate for data, total monthly cost is just the Norgate sub (~$53/mo) once AmiBroker is paid for |
| **Cons** | Older Windows-centric platform; AFL has its own learning curve; less Python-friendly |
| **Fit** | Strong if the developer is open to writing AFL instead of Python. Total cost over 3 years is dramatically lower than other options. |
| **URL** | <https://www.amibroker.com/products.html> |

#### C3. TC2000

| Aspect | Detail |
|---|---|
| **Cost** | Basic $24.99/mo, **Premium $49.99/mo**, Premium+ $99.99/mo (real-time US) |
| **Commercial use** | OK |
| **P&F support** | Native, strong |
| **API** | Proprietary scripting (PCF — Personal Criteria Formula); **no public REST API** |
| **Pros** | Affordable; popular among technical traders; familiar interface |
| **Cons** | No programmatic API for our daily-cron workflow; would require manual export or Excel/PCF-driven scans |
| **Fit** | Not a good fit for an automated headless screener |
| **URL** | <https://www.tc2000.com/Pricing> |

#### C4. TradingView — **NOT a fit; here for completeness**

| Aspect | Detail |
|---|---|
| **Cost** | Essential $12.95/mo, Plus $29.95, Premium $59.95, Ultimate $199.95 |
| **API** | **No public data API; ToS prohibits scraping.** Webhook alerts only. |
| **Fit** | Not viable for an automated screener. Skip. |
| **URL** | <https://www.tradingview.com/pricing/> |

#### C5. NinjaTrader

| Aspect | Detail |
|---|---|
| **Cost** | Platform free; live $99/mo or $1,499 lifetime + equity data via Kinetick (~$55/mo non-pro) |
| **API** | NinjaScript (C#); largely futures-focused |
| **Fit** | Equity P&F support is limited; not a strong fit |
| **URL** | <https://ninjatrader.com/pricing/> |

#### C6. Sierra Chart

| Aspect | Detail |
|---|---|
| **Cost** | Standard $26/mo, Advanced $36/mo, Integrated Advanced $56/mo, + data feed |
| **API** | DTC protocol + ACSIL (C++) — heavyweight integration |
| **Fit** | Futures-skewed; not suited to a daily equity screener |
| **URL** | <https://www.sierrachart.com/index.php?page=doc%2FPackages.php> |

---

### D. Specialty / TA services — **NOT a fit; ToS prohibits automation**

#### D1. Investors.com / IBD

| Aspect | Detail |
|---|---|
| **Cost** | IBD Digital $449/yr; **IBD MarketSurge $149.95/mo or $1,499/yr**; Leaderboard $699/yr |
| **API** | **No public API; ToS prohibits automated scraping** |
| **Fit** | Not viable for an automated screener — skip |

#### D2. StockCharts.com

| Aspect | Detail |
|---|---|
| **Cost** | Basic $19.95, Extra $29.95, Pro $49.95/mo |
| **API** | **No public API; ToS prohibits scraping** |
| **Fit** | Not viable — skip |

---

### E. Institutional — out of scope for this project, listed for completeness

#### E1. Bloomberg Terminal

| Aspect | Detail |
|---|---|
| **Cost** | **~$31,980/seat/yr** (single seat), 2-year minimum |
| **Fit** | Out of scope. Mentioned because it's the institutional standard. |

#### E2. FactSet

| Aspect | Detail |
|---|---|
| **Cost** | $4K–$50K/user/year depending on package |
| **Fit** | Out of scope; institutional only |

#### E3. LSEG Workspace (Refinitiv Eikon)

| Aspect | Detail |
|---|---|
| **Cost** | ~$1,500–$3,000/user/month |
| **Fit** | Out of scope; institutional only |

---

## Side-by-side: what Norgate-only delivers vs what NDWEQTA delivers

A common question: if we go with the Norgate-only path to save cost, what specifically do we lose versus NDWEQTA? The honest answer is: **only DWA's proprietary Technical Attributes composite score (0–5).** Everything else can be computed by our P&F engine from Norgate's OHLC.

| Technical analysis output | Norgate-only | NDWEQTA |
|---|---|---|
| Daily OHLC for full US equities | ✅ Norgate | ❌ (needs separate OHLC vendor) |
| Historical OHLC + survivorship-bias-free history | ✅ Norgate | ❌ |
| P&F chart construction (X/O cells, columns) | ✅ Our P&F engine from OHLC | ✅ Our P&F engine from OHLC |
| P&F signal status (DT/TT/catapult/etc.) | ✅ Our signal detectors | ✅ Direct from DWA |
| P&F trend posture (above support / below resistance) | ✅ Our trendline logic | ✅ Direct from DWA |
| Relative Strength chart vs SPXEWI/RSP | ✅ Our RS engine | ✅ Direct from DWA |
| Long-term RS buy/sell signal | ✅ Our RS engine | ✅ Direct from DWA |
| Bullish Percent Index (universe + sectors) | ✅ Our aggregation | ❌ **Not in NDWEQTA either** — we compute it ourselves regardless of path |
| Sector classifications | ✅ Norgate's tags or GICS | ⚠️ DWA's proprietary DALI sectors (possibly — unclear) |
| **DWA Technical Attributes composite score (0–5)** | ❌ **Cannot reproduce — formula is proprietary** | ✅ Direct from DWA |
| Pre-momentum patterns + scoring | ✅ Phase 4 implementation | ✅ Phase 4 implementation |
| In-momentum patterns + scoring | ✅ Phase 4 implementation | ✅ Phase 4 implementation |

### The Technical Attributes gap and the internal-composite workaround

The TA score gap is the only meaningful loss in a Norgate-only path. The bot can compute a **functionally equivalent internal composite** that captures the same posture concept by tallying favorable conditions:

- On a P&F buy signal? +1
- Above bullish support line? +1
- RS chart on a long-term buy signal? +1
- Positive RS trend? +1
- In a sector with favorable BPI state? +1

This produces a transparent 0–5 score using rules the bot can show on every report. It will not match DWA's exact TA number on any given stock — DWA's exact formula is proprietary — but it captures the same posture concept and should correlate strongly with DWA's TA in practice.

The advisor retains the ability to cross-check the bot's internal composite against DWA's authoritative TA score by spot-checking names in his existing NDW Research Platform subscription (which he keeps regardless of the API decision).

### When does the TA gap matter?

- **If the advisor uses TA *directionally*** (just wants a quick read on whether a stock is technically strong by DWA's measure): the internal composite is a reasonable substitute. Go Norgate-only.
- **If the advisor uses TA *quantitatively*** (e.g., specific rules like "I only buy TA = 5"): the authoritative value matters. Apply the threshold table — license NDWEQTA if it prices under ~$300/mo.

This is a useful question to confirm with the advisor before the NDWEQTA pricing decision is finalized.

---

## Updated recommendation hierarchy

Now armed with the comprehensive pricing, here is the revised pick order:

### If NDWEQTA quote is competitive (< ~$300/month)

License NDWEQTA + **pair with Alpaca Algo Trader Plus ($99/mo) or Norgate Platinum ($53/mo) for OHLC**. Total: $150–$400/mo. Best fidelity to DWA conventions, authoritative signals as source-of-truth, and OHLC for chart visualization and backtesting.

### If NDWEQTA quote is high (> ~$300/month) — recommended path

**Pure replication, two-vendor stack:**

- **Norgate Data Platinum ($53/mo)** as primary OHLC source — best-in-class historical data, survivorship-bias-free backtesting, clean commercial license
- **Alpaca Algo Trader Plus ($99/mo)** as real-time/intraday source if needed for the daily refresh — or use Norgate end-of-day only
- **Advisor's existing NDW Research Platform subscription** (already paid for) as a weekly manual cross-check on the bot's top candidates

Total: **~$50–$150/mo**. Build the full P&F + RS + BPI + pre-momentum/in-momentum engine ourselves per the methodology docs.

### If a clean defined commercial license is paramount

**EODHD Commercial Internal-Use plan ($399/mo)** as a single-vendor OHLC source. More expensive than the Norgate + Alpaca stack but explicitly licensed for the exact use case, no gray areas.

### If absolute minimum cost matters

**Marketstack Basic ($9.99/mo) + AmiBroker ($299 one-time) + Norgate ($53/mo)** = ~$63/mo after the first month. Trade-off: AmiBroker workflow is Windows-centric and AFL-based rather than Python-based, but the cost savings are real.

### What to skip entirely

- **Polygon.io individual/retail tiers** — ToS prohibits commercial use; only their Business tier (sales-quote) is usable
- **Tiingo Power tier** — also individual-use only; Commercial requires a sales quote
- **TradingView / StockCharts / IBD / TC2000** — no public APIs or ToS prohibits automation; not viable for an automated screener
- **Bloomberg / FactSet / LSEG** — institutional-only; far beyond budget for this project

---

## What this means for total project cost

| Configuration | Estimated monthly | Notes |
|---|---|---|
| **NDWEQTA (cheap tier) + Norgate** | **~$100–$150** | Best fidelity; depends on NDWEQTA pricing |
| **NDWEQTA (mid tier) + Alpaca** | **~$300** | Marginal |
| **Pure replication: Norgate + advisor weekly check** | **~$53** | Strongest cost-driven choice |
| **Pure replication: Norgate + Alpaca + advisor weekly check** | **~$152** | Adds real-time data on top |
| **EODHD Commercial only** | **~$399** | Cleanest single-vendor license |
| **AmiBroker stack** | **~$63 after first month** | Lowest ongoing cost; different developer workflow |

The pure-replication path is dramatically cheaper than even the cheapest NDWEQTA tier and is now the **default fallback** unless NDWEQTA pricing surprises on the low end.

---

## Pre-purchase checklist (whatever path is chosen)

For each vendor under serious consideration, verify before signing:

1. **Commercial use language in the ToS** — specifically for an advisor's automated screening tool
2. **Universe coverage** — does it cover all NYSE + NASDAQ-listed common stocks? Including small-caps?
3. **Adjustment quality** — split and dividend adjustments are correct and applied across the full history
4. **History depth** — at least 5 years for daily backtesting; 20+ years preferred for regime-change studies
5. **Rate limits** — adequate for a daily refresh of ~6,000 tickers in a single overnight run
6. **API stability / SLA** — what happens when the vendor has an outage? Is there a status page?
7. **Trial period** — most quality vendors offer a 7- to 30-day trial; use it to verify data quality before committing

---

## Sources

- [Polygon.io pricing](https://polygon.io/pricing) and [Polygon Commercial Use Terms PDF](https://polygon.io/legal/Commercial_Use_Terms.pdf)
- [Tiingo pricing](https://www.tiingo.com/about/pricing)
- [EOD Historical Data commercial pricing](https://eodhd.com/commercial-pricing)
- [Alpha Vantage premium plans](https://www.alphavantage.co/premium/)
- [Finnhub pricing](https://finnhub.io/pricing)
- [Twelve Data pricing](https://twelvedata.com/pricing)
- [Marketstack pricing](https://marketstack.com/pricing)
- [Intrinio pricing](https://intrinio.com/pricing)
- [Norgate Data prices](https://norgatedata.com/prices.php)
- [Interactive Brokers market data pricing](https://www.interactivebrokers.com/en/pricing/market-data-pricing.php)
- [Schwab Trader API developer portal](https://developer.schwab.com/)
- [Alpaca Markets data plans](https://alpaca.markets/data)
- [Optuma portal](https://portal.optuma.com/store/optuma-professional-services-subscription/)
- [TC2000 pricing](https://www.tc2000.com/Pricing)
- [TradingView pricing](https://www.tradingview.com/pricing/)
- [NinjaTrader pricing](https://ninjatrader.com/pricing/)
- [AmiBroker products](https://www.amibroker.com/products.html)
- [IBD MarketSurge](https://traderhq.com/investors-business-daily-digital-review-guide/) (via third-party review)
- [Sierra Chart packages](https://www.sierrachart.com/index.php?page=doc%2FPackages.php)
- [StockCharts.com pricing](https://stockcharts.com/pricing/)
- [Bloomberg Terminal seat cost (third-party data)](https://costbench.com/software/financial-data-terminals/bloomberg-terminal/)
- [FactSet pricing overview](https://www.factset.com/factset-pricing)
- [LSEG Workspace](https://www.lseg.com/en/data-analytics/products/workspace)
