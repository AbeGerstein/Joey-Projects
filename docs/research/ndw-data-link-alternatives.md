# Research: Alternatives to Nasdaq Data Link NDWEQTA

**Triggered:** 2026-05-16, after the advisor's pivot to (a) pure P&F screening with no fundamental filter and (b) pre-momentum detection as the explicit predictive intent. Both pivots change the cost calculus on NDWEQTA — see *Why this matters now* below.

This document evaluates alternatives to licensing the Nasdaq Data Link NDWEQTA database in case the sales quote (currently pending the callback from Nasdaq on 2026-05-16) comes in at a price tier that doesn't justify the spend.

---

## Why this matters now

When NDWEQTA was first proposed as the data source ([decisions log 2026-05-16](../01-decisions-log.md#2026-05-16--dwa-access-path-nasdaq-data-link-ndw-database-provisional-pending-pricing-partial-oq-002)), it was the obvious choice because the advisor relied on DWA's proprietary **Technical Attributes (TA) composite score**, which only NDWEQTA can deliver programmatically. That made NDWEQTA functionally required.

Two subsequent decisions have weakened that requirement:

1. **The fundamental filter was removed entirely** — the bot is now pure P&F. This shrinks the data footprint and removes the FMP / SimFin dependency.

2. **The predictive intent is now explicitly pre-momentum** — the bot is looking for stocks *before* they enter momentum, not the strong stocks already in motion. **The TA score is designed for the opposite question**: it identifies stocks already on buy signals with strong RS. Per [methodology/pre-momentum-detection.md](../methodology/pre-momentum-detection.md), a high TA score on an extended chart is now an **anti-signal** in this screener. The TA score is still useful (as a contrarian filter — "TA = 5 + extended chart → exclude"), but it's no longer the prize.

What NDWEQTA still uniquely gives us: **authoritative DWA signal status, RS rankings, and the TA score field** (for use as an anti-pattern detector). Everything else (BPI, sector classifications, raw chart data) we already need to compute or source ourselves regardless.

**New cost-justification thresholds for NDWEQTA (revised 2026-05-16):**

| NDWEQTA monthly cost | Decision |
|---|---|
| < $100 | License it — cheap insurance, advisor familiarity, signal cross-check |
| $100–$300 | License it but evaluate carefully — depends on whether the advisor uses the TA score in workflow |
| $300–$700 | Lean against — replicate from OHLC; revisit if Phase 4 backtest shows the TA score adds material edge |
| > $700 | Skip — replicate from OHLC, use the advisor's existing platform manually for spot-checks |

(These thresholds are working judgments by Claude — not advisor-confirmed. The advisor should review them before committing.)

---

## The alternatives (in order of recommendation)

### Option 1: Pure replication from raw OHLC (recommended primary alternative)

Build the complete pipeline from raw price data — Polygon.io or Tiingo as the OHLC vendor, our custom P&F engine for everything technical.

| Aspect | Detail |
|---|---|
| **OHLC vendor** | Polygon.io Stocks Starter (~$29/mo) or Tiingo (~$10–$30/mo) |
| **What we build ourselves** | P&F chart construction, all signal detectors, RS charts vs SPXEWI/RSP, BPI for universe and sectors, pre-momentum scoring |
| **What we get from raw data** | OHLC for ~6,000 US equities, adjusted for splits and dividends |
| **Sector classifications** | GICS from any equity-data vendor (Polygon provides), or FRED's NQ-DALI series for DWA-style sectors |
| **What we cannot reproduce** | DWA's proprietary Technical Attributes composite score, DWA's exact universe definitions for sector indexes, DWA's "Fund Score" for ETFs (out of scope anyway) |
| **Cost** | ~$30–$40/month total |
| **Build effort** | Highest of the alternatives — the P&F engine is real work — but we are building it anyway |
| **Best for** | Any case where NDWEQTA pricing exceeds the threshold above, or where full transparency / customization is valuable |

**Strongest argument for this option:** with the project's pivot away from the TA score as a primary input, this is the cleanest architecture. We own the entire signal logic. We can implement the pre-momentum patterns exactly as we want them. There is no licensing friction.

**Risks:** our P&F engine's signal output must match Dorsey's conventions faithfully. Mitigation: extensive unit tests against textbook examples from the book; cross-validation against the advisor's manual chart reads on a sample of names; quarterly spot-checks against the advisor's NDW platform.

### Option 2: Hybrid — replicate primary, advisor's existing NDW platform as a weekly cross-check

Identical to Option 1 for the daily-bot architecture. *Additionally,* the advisor uses their existing NDW Research Platform subscription (already paid for, separate from any API license) to manually pull a small sample (e.g., 20 names from the bot's top candidates) weekly and compare against the bot's signal output. If the bot's signals diverge meaningfully from DWA's platform signals, that's a bug we investigate.

| Aspect | Detail |
|---|---|
| **Incremental cost** | Zero — uses subscription the advisor already has |
| **Operational cost** | ~15 minutes/week of the advisor's time |
| **Value** | High — gives ongoing confidence that our replication matches DWA's authoritative output without licensing the feed |

This is the **strongest practical option** when NDWEQTA pricing is unfavorable. It captures most of the validation benefit of NDWEQTA without the cost.

### Option 3: Optuma

Optuma is a charting and analysis platform that natively implements P&F, RS charts, and Bullish Percent indicators methodologically. It is not DWA-branded but follows the same conventions described in Dorsey's book.

| Aspect | Detail |
|---|---|
| **Cost** | Approximately $50–$150/month for individual subscriptions; higher tiers for institutional |
| **API** | Higher-tier plans include scripting and API access; verify with Optuma |
| **P&F fidelity** | High — Optuma's P&F construction follows traditional scaling and 3-box reversal conventions |
| **What we save** | We don't have to build the chart-construction engine; can lean on Optuma's tested implementation |
| **What we give up** | Lock-in to their platform; less customization than building ourselves; their signal definitions may not match Dorsey's exact wording |
| **Best for** | A team that wants to avoid building the P&F engine entirely |

For this project, given we have one developer building from scratch and need the predicate logic for pre-momentum patterns customized, Optuma is **less attractive than Option 1**. The cost of Optuma can equal or exceed NDWEQTA at midrange tiers, while giving us less proprietary value.

### Option 4: Norgate Data + custom P&F engine

Norgate is a specialist in clean historical data for systematic backtesting. Best-in-class for **point-in-time index constituents** (Russell 3000 / S&P 500 as of any historical date) and survivorship-bias-free backtesting.

| Aspect | Detail |
|---|---|
| **Cost** | ~$25–$60/month equivalent for relevant tiers |
| **API** | Python integration via their desktop app's bindings |
| **Strength** | Point-in-time historical universe data — the single biggest gap in retail OHLC vendors |
| **Use case** | Either as the primary OHLC source if Phase 4 backtest fidelity matters most, or as a Phase 4-only add-on alongside Polygon for the live screener |

Not a complete alternative to NDWEQTA on its own — pair it with our P&F engine. Consider adding it in Phase 4 regardless of which primary path we take, because backtest survivorship bias is a real concern when the universe is the full US equity market.

### Option 5: TC2000

A popular technical-analysis platform among retail traders. Has P&F support and a streaming data API in higher tiers.

| Aspect | Detail |
|---|---|
| **Cost** | $30–$90/month depending on tier |
| **API** | Available but more retail-trader oriented than developer-focused |
| **P&F fidelity** | Adequate but not as customizable as Optuma or our own engine |
| **Best for** | Skipped — Option 1 or Option 3 dominates |

### Option 6: StockCharts.com

No public API; web-only platform. **Not viable** for automation. Skipped.

### Option 7: TradingView

Strong charting platform with a Pine Script ecosystem and a screener API. P&F support exists but is community-maintained and inconsistent.

| Aspect | Detail |
|---|---|
| **Cost** | $15–$60/month |
| **API** | Limited; mostly works for chart embedding and basic screens |
| **P&F fidelity** | Community plugins of variable quality |
| **Best for** | Skipped — quality and customization don't meet the project's needs |

---

## Recommendation hierarchy

Based on the revised cost thresholds in the *Why this matters now* section:

1. **If NDWEQTA quote ≤ $100/month:** license it. Use NDWEQTA's signals as source of truth, our P&F engine for chart visualization and BPI/pre-momentum logic. Best of both worlds.

2. **If NDWEQTA quote is $100–$300/month:** marginal call. Discuss with the advisor — if they value the TA score as a confirmation tool and the platform familiarity, license it. If they're indifferent, go to Option 1 + Option 2.

3. **If NDWEQTA quote > $300/month:** go directly to **Option 1 (pure OHLC replication) + Option 2 (weekly platform spot-check)**. This is the strongest configuration when the proprietary feed cost exceeds clean justification. Add Option 4 (Norgate) in Phase 4 for backtest fidelity.

4. **In all scenarios** — Option 4 (Norgate) is worth adding in Phase 4 regardless, because the backtest universe needs point-in-time accuracy.

---

## What this means for the project's monthly cost

| Configuration | Estimated monthly cost |
|---|---|
| **NDWEQTA (cheap tier) + Polygon + hosting** | $30 OHLC + $50 NDWEQTA + $10 hosting = **~$90/month** |
| **NDWEQTA (mid tier) + Polygon + hosting** | $30 OHLC + $200 NDWEQTA + $10 hosting = **~$240/month** |
| **Option 1 only (Polygon + hosting)** | $30 + $10 = **~$40/month** |
| **Option 1 + Norgate in Phase 4** | $40 base + $40 Norgate add = **~$80/month** |
| **Option 1 + Option 2 (advisor weekly check)** | $40 + zero incremental = **~$40/month** |
| **Optuma (mid tier) + hosting** | $100 + $10 = **~$110/month** |

The replication path is dramatically cheaper than even the cheapest NDWEQTA tier and is now the *default* path unless NDWEQTA pricing surprises on the low side.

---

## Sources

- [Polygon.io](https://polygon.io) — OHLC vendor
- [Tiingo](https://www.tiingo.com) — OHLC vendor
- [Norgate Data](https://norgatedata.com) — survivorship-bias-free historical data
- [Optuma](https://www.optuma.com) — P&F-capable analysis platform
- [TC2000](https://www.tc2000.com) — technical-analysis platform
- [TradingView](https://www.tradingview.com) — charting platform
- [Existing methodology docs](../methodology/) — what we'd need to implement ourselves under Option 1
- [research/dwa-access.md](dwa-access.md) — original DWA access investigation
- [research/ndw-data-link-pricing.md](ndw-data-link-pricing.md) — NDWEQTA coverage and pricing detail
