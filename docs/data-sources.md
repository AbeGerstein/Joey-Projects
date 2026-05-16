# Data Sources Evaluation

This document evaluates the data vendors available for each data category the bot needs. Final vendor selections are pending — they depend on resolved open questions ([OQ-002](02-open-questions.md#oq-002-dwa-access-path), [OQ-003](02-open-questions.md#oq-003-stock-universe)) and on budget.

The bot needs three data categories:

1. **OHLC** (open, high, low, close, volume) — the raw price data that feeds P&F construction. Adjusted for splits and dividends.
2. **Fundamentals** — financial statements and standard ratios for the universe.
3. **DWA-specific data** (signals, RS rankings, BPI) — only if we choose options A or B in [OQ-002](02-open-questions.md#oq-002-dwa-access-path). Not needed if we replicate from raw OHLC.

Plus a few small inputs: index data (SPXEWI for RS calculations), sector tags (GICS or similar), earnings calendar.

---

## 1. OHLC vendors

### Polygon.io (recommended for v1)

| Aspect | Detail |
|---|---|
| **Coverage** | Full US equities (NYSE, NASDAQ, OTC); end-of-day and intraday |
| **History** | 20+ years of daily OHLC; intraday goes back further than most |
| **Adjustments** | Split-adjusted; dividend-adjusted available via separate endpoint |
| **API quality** | Modern REST, well-documented, generous rate limits on the Stocks Starter tier |
| **Cost** | Stocks Starter is ~$29/month at the time of writing; higher tiers up to enterprise |
| **Universe coverage** | Single ticker fetches; bulk endpoints for full-market snapshots |
| **Reliability** | Generally well-regarded among independent developers |
| **Quirks** | Some thinly-traded tickers have gaps; check before relying on them |

**Recommended tier:** Stocks Starter. Sufficient for end-of-day screening of a Russell 3000 universe.

URL: <https://polygon.io>

### Tiingo

| Aspect | Detail |
|---|---|
| **Coverage** | US equities + a growing global set |
| **History** | 30+ years of daily OHLC |
| **Adjustments** | Adjusted prices native (well-curated) |
| **API quality** | Solid REST, well-documented |
| **Cost** | $10–$30/month for the relevant tier |
| **Universe coverage** | Single-ticker focus; bulk-download endpoints available |
| **Reliability** | Strong reputation for adjustment quality |
| **Quirks** | Less granular intraday history than Polygon |

URL: <https://www.tiingo.com>

### EOD Historical Data (EODHD)

| Aspect | Detail |
|---|---|
| **Coverage** | US + international; very broad |
| **History** | 30+ years |
| **Adjustments** | Adjusted prices |
| **API quality** | REST, reasonable documentation |
| **Cost** | ~$20–$50/month for the relevant tier |
| **Universe coverage** | Bulk download supported |
| **Reliability** | Decent; some sporadic data-quality complaints in community channels |
| **Quirks** | Adjustment methodology occasionally non-standard |

URL: <https://eodhistoricaldata.com>

### Norgate Data

| Aspect | Detail |
|---|---|
| **Coverage** | US + some global; specializes in clean historical data for backtesting |
| **History** | Deep — designed for systematic-trading research |
| **Adjustments** | Point-in-time adjusted prices; **point-in-time index constituents** (the strongest reason to consider Norgate) |
| **API quality** | Desktop application + Python bindings; less of a modern REST API |
| **Cost** | Higher — typically $300–$700/year |
| **Universe coverage** | Excellent for historical universes (Russell 3000 as it stood on date D) |
| **Reliability** | Excellent for survivorship-bias-free backtesting |
| **Quirks** | Installation is heavier than a pure-API vendor |

URL: <https://norgatedata.com>

### yfinance (NOT for production)

Free Python wrapper around Yahoo Finance. Useful for prototyping and quick spot-checks but **not** for production:

- No reliability SLA
- Rate-limited unpredictably
- Adjustment quality is inconsistent across the curve
- Yahoo can break the underlying endpoint at any time

Acceptable for early Phase 2 prototyping of the P&F engine; replace with a real vendor before Phase 4 backtesting.

---

## Recommendation for OHLC

**Polygon.io Stocks Starter for v1**, with Norgate as a serious consideration if the backtest in Phase 4 needs survivorship-bias-free historical universes. The decision can be deferred until Phase 4.

---

## 2. Fundamentals vendors

### Financial Modeling Prep (recommended for v1)

| Aspect | Detail |
|---|---|
| **Coverage** | US + global; income statement, balance sheet, cash flow, ratios |
| **History** | 20+ years |
| **API quality** | REST, well-documented, ergonomic |
| **Cost** | Starter tiers $20–$30/month |
| **Quirks** | Some custom-computed ratios use slightly non-standard definitions — spot-check against EDGAR for the metrics that matter most |

URL: <https://site.financialmodelingprep.com>

### SimFin

| Aspect | Detail |
|---|---|
| **Coverage** | US + global |
| **History** | 10+ years |
| **API quality** | REST + bulk download |
| **Cost** | Free tier exists; paid is $20+/month |
| **Quirks** | Smaller universe than FMP; data is clean but coverage is less complete |

URL: <https://simfin.com>

### SEC EDGAR (authoritative fallback)

The primary source. The SEC's EDGAR system contains every 10-K, 10-Q, and 8-K filing directly. Free to access, but raw — XBRL parsing required. Best used as:

- The **authoritative source** when a vendor's number looks suspect
- The source of **earnings dates** and **insider transactions** (Form 4)
- The fallback if vendors are temporarily unavailable

URL: <https://www.sec.gov/edgar.shtml>; API: <https://www.sec.gov/edgar/sec-api-documentation>

### Alpha Vantage

A serviceable option historically; current limits feel tight for our use case. Mentioned for completeness; not recommended over FMP or SimFin.

URL: <https://www.alphavantage.co>

---

## Recommendation for fundamentals

**Financial Modeling Prep for v1**, with EDGAR as the authoritative spot-check source for any specific metric whose value seems off.

---

## 3. DWA-specific data

See [research/dwa-access.md](research/dwa-access.md) for the full evaluation.

- **Option A: Nasdaq Data Link NDW database** — paid, separately licensed, highest fidelity
- **Option B: Manual CSV exports** from the advisor's existing NDW platform subscription — no extra cost, requires manual step
- **Option C: Replicate from raw OHLC** — no DWA cost, no manual step, slightly lower fidelity (no proprietary "Technical Attributes" score)

**Current recommendation:** Option C for v1. Decision pending in [OQ-002](02-open-questions.md#oq-002-dwa-access-path).

---

## 4. Auxiliary data

### S&P 500 Equal Weighted Index (SPXEWI)

Needed for RS calculations. Two options:

- **Direct index data** from Polygon.io or similar (may require an extra subscription)
- **Proxy via RSP ETF** — the equal-weight S&P 500 ETF. Tracks SPXEWI essentially perfectly. Available from any equity OHLC vendor. **Recommended** — eliminates the need for a separate index subscription.

### Sector tags

GICS classifications are the standard. Sources:

- **From the fundamentals vendor** (FMP, SimFin) — both tag each ticker with sector and industry
- **MSCI / S&P** — license required for the canonical GICS tree (not necessary for our purposes; vendor tags are sufficient)

### Earnings calendar

Needed for catalyst flags. FMP includes earnings dates; alternatively, Earnings Whispers and Zacks both have APIs. FMP is sufficient.

### Insider transactions (Form 4 filings)

For the optional insider-buying catalyst flag. SEC EDGAR has these directly; several free wrappers exist for parsing them.

---

## Cost summary (working assumptions)

| Category | Vendor | Monthly cost |
|---|---|---|
| OHLC | Polygon.io Stocks Starter | ~$29 |
| Fundamentals | FMP Starter | ~$25 |
| DWA data | Replicate from OHLC (no cost) | $0 |
| Auxiliary | All covered by above | $0 |
| **Total** | | **~$54/month** |

Optional upgrades:
- Norgate Data for survivorship-bias-free backtest: +$25-60/month equivalent
- Nasdaq Data Link NDW database: TBD per sales quote
- Higher Polygon.io tier if intraday becomes needed: +$50-100/month

---

## Vendor selection process

Don't commit to vendor subscriptions until Phase 0 is complete and [OQ-002](02-open-questions.md#oq-002-dwa-access-path) and [OQ-003](02-open-questions.md#oq-003-stock-universe) are resolved. Once those are settled:

1. Provision Polygon.io and FMP starter accounts.
2. Spend a few days running data-quality checks on a small ticker sample (~50 names) before committing to the full universe.
3. Verify that the data we're getting actually produces sensible P&F charts and RS series.
4. Then scale up to the full universe.

---

## References

- [Polygon.io documentation](https://polygon.io/docs)
- [Tiingo documentation](https://www.tiingo.com/documentation/general/overview)
- [EOD Historical Data documentation](https://eodhistoricaldata.com/financial-apis/)
- [Norgate Data — Python integration](https://norgatedata.com/python-introduction.php)
- [Financial Modeling Prep documentation](https://site.financialmodelingprep.com/developer/docs)
- [SimFin documentation](https://simfin.com/data/access/api)
- [SEC EDGAR API](https://www.sec.gov/edgar/sec-api-documentation)
