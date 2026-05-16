# Methodology: Relative Strength (DWA Convention)

Relative Strength (RS) is the second pillar of Dorsey Wright's methodology, alongside P&F itself. The core idea: don't just ask whether a stock is going up — ask whether it's going up *faster than the market* (or faster than its sector). Stocks with positive RS tend to keep outperforming; stocks with negative RS tend to keep underperforming. RS is the trend behind the trend.

This document follows the DWA convention as documented publicly and as taught in Dorsey's *Point and Figure Charting*.

---

## The RS ratio

The RS line is the ratio of a security's price to a benchmark, multiplied by 100:

```
RS = (Security price / Benchmark price) × 100
```

When the ratio rises, the security is outperforming the benchmark; when it falls, it's underperforming.

### Choice of benchmark

DWA uses the **S&P 500 Equal Weighted Index (SPXEWI)** as the standard benchmark for stock RS. The equal-weighted variant is preferred over the cap-weighted S&P 500 because:

1. The equal-weighted index represents the "average stock" more faithfully — a few mega-caps don't dominate it.
2. Outperforming the equal-weighted index is a tougher and more meaningful bar than beating a cap-weighted index in a mega-cap-led market.

For **fund RS**, DWA uses the same SPXEWI benchmark with adjusted scaling (see below).

For **sector RS**, an additional RS chart is sometimes computed using the sector's own index as the benchmark — to identify the leading stocks *within* a sector.

---

## RS as a P&F chart

DWA does not look at the RS line as a continuous time-series chart. They plot it as a **P&F chart in its own right**, using:

| Parameter | Value |
|---|---|
| Box scaling | **Percentage** (not traditional) |
| Box size for stocks | **6.5%** |
| Box size for funds | **3.25%** |
| Reversal | **3-box** |
| Construction method | High/low (same as price P&F) |

The P&F treatment filters out noise in the RS ratio and produces the same kind of clean signal structure as the price chart.

---

## RS signals

RS signals are interpreted on long time horizons — usually months to years. They are *not* tactical trade signals; they're durable regime indicators.

| Signal | Definition | Interpretation |
|---|---|---|
| **Long-term RS buy signal** | The RS column of X's exceeds the prior X-column high on the RS P&F chart | The stock has entered a period of sustained outperformance versus the benchmark |
| **Long-term RS sell signal** | The RS column of O's drops below the prior O-column low | The stock has entered a period of sustained underperformance |
| **Positive RS trend** | RS chart is above its 45° bullish support line | Outperformance is structurally intact |
| **Negative RS trend** | RS chart is below its 45° bearish resistance line | Underperformance is structurally intact |

A stock can be on a price-chart buy signal while on an RS sell signal, or vice versa. The combined posture is what matters — Dorsey's framework heavily favors stocks that are positive on **both** their price chart and their RS chart.

---

## How RS is used in this project

The screener uses RS in three ways:

1. **As a filter:** stocks on a long-term RS sell signal are deprioritized or excluded outright. The bot is looking for *leaders*, not laggards.
2. **As a tiebreaker / score input:** among candidates with comparable price-chart setups, those with stronger RS rank higher in the composite score.
3. **As a sector overlay:** sector RS (sector vs. SPXEWI) is used to identify which sectors are in favor. Candidates from in-favor sectors score higher (sector tailwind effect documented in [bullish-percent-index.md](bullish-percent-index.md)).

---

## RS Matrix

DWA's "Relative Strength Matrix" tool ranks every stock in a universe against every other stock by RS. The matrix is computed by:

1. For each pair (A, B), compute the RS chart of A vs. B (same 6.5% scaling).
2. Determine whether A is currently on a long-term buy or sell signal against B.
3. A stock's RS rank is roughly the number of pairs in which it is on a buy signal.

The top decile of the matrix is the universe's strongest stocks on a peer-relative basis. DWA exposes this in their platform as a sortable RS rank.

This project will implement the RS Matrix in Phase 2 as part of the P&F engine. It is computationally non-trivial (O(N²) ratios per universe), but for a 3,000-name universe it's still tractable (~4.5M pairs, computable in seconds with vectorized pandas).

---

## Edge cases and pitfalls

- **Stock splits and dividends:** RS calculations must use **adjusted prices** to avoid spurious signals on split dates. The data vendor must provide adjusted OHLC.
- **Index choice:** if the data vendor doesn't carry SPXEWI directly, the equal-weighted S&P 500 ETF (ticker **RSP**) is a perfect proxy.
- **Currency:** non-US ADRs introduce currency effects in the RS ratio. The project's hard scope is US equities only, so this shouldn't arise, but it's worth flagging if scope ever expands.
- **Sparse data:** newly listed stocks have insufficient history for a meaningful long-term RS chart. Apply a minimum history filter (e.g., 2 years of price data) before computing RS.

---

## References

- [DWA — Relative Strength Basics](https://nasdaqdorseywright.zendesk.com/hc/en-us/articles/15938757529869-Relative-Strength-Basics) (the canonical public source for DWA's RS methodology)
- [DWA — Relative Strength Matrix Basics](https://nasdaqdorseywright.zendesk.com/hc/en-us/articles/19226088223373-Relative-Strength-Matrix-Basics)
- Dorsey, *Point and Figure Charting*, chapter on Relative Strength.
- [Nitrogen Wealth — P&F + RS Signals whitepaper](https://nitrogenwealth.com/wp-content/uploads/2022/12/Pnf_RS_Signals_Whitepaper.pdf) — useful independent overview.
