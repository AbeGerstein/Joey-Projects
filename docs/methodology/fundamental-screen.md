# Methodology: Fundamental Initial Filter — SUPERSEDED 2026-05-16

> **STATUS: This document is retained for the audit record only. The fundamental filter has been removed from the project entirely.**
>
> On 2026-05-16, the advisor determined fundamental screening adds no edge to this screener — the P&F chart already reflects fundamental weakness via supply and demand (buyers stay away from bad fundamentals, the chart shows it). The bot is now a pure P&F / supply-and-demand screener. See [decisions log entry](../01-decisions-log.md#2026-05-16--fundamental-filter-removed-entirely-supersedes-the-oq-004-default).
>
> The content below describes the filter design as originally scoped. It is not in the production design.

---

The fundamental layer of this project plays a **specific, limited role**: it is a *junk-rejection gate* that runs before P&F evaluation, narrowing the universe to companies whose financial health is sound enough to be worth charting. It is not a scoring engine, and it does not drive ranking. The advisor's edge is P&F; this gate exists to make sure the bot doesn't waste P&F evaluation cycles on companies that have no business being recommended on fundamentals alone.

This document captures the design framework and the criteria options. The exact thresholds are pending advisor input — see [OQ-004](../02-open-questions.md#oq-004-fundamental-filter-criteria).

---

## Why the filter is narrow

Dorsey's view in *Point and Figure Charting* is consistent throughout: fundamentals tell you *what* to consider; supply and demand (the P&F chart) tells you *when* and *whether*. A fundamentally weak company can still be a great long-side trade if the P&F chart says demand is overwhelming supply — and a fundamentally beautiful company can lose money for years if the chart says supply is in control.

This project's design respects that view. The fundamental filter is not trying to find the best companies on a fundamental basis; it is trying to **eliminate the small fraction of names where the fundamentals are bad enough to suggest the stock is structurally broken** — pre-bankruptcy candidates, persistent cash-bleeders, accounting-question names, etc. Everything else passes through to P&F evaluation.

If the filter is too strict, the bot loses access to legitimate turnaround setups — which are some of P&F's biggest wins. If it's too loose, the bot churns chart-analysis cycles on names that shouldn't be in a long-only advisor's screen. The right calibration is narrow.

---

## Filter design options

These are four shapes the filter could take, from most permissive to most strict. The advisor's preference is captured in [OQ-004](../02-open-questions.md#oq-004-fundamental-filter-criteria).

### Option A — Quality gate only (most permissive)

A stock passes if it meets all of:

| Criterion | Threshold (working assumption) | Rationale |
|---|---|---|
| Trailing-twelve-month free cash flow | Positive | Excludes persistent cash-bleeders |
| Return on equity (TTM) | > 0 | Excludes loss-makers on a return basis |
| Debt / Equity | < 3.0 | Excludes highly leveraged names where the equity is essentially an option |
| Has reported financials in last 2 quarters | Yes | Excludes companies that have stopped filing or have suspect data |

This option eliminates roughly 15–25% of a typical broad-market universe — mostly small-cap loss-makers and a handful of distressed names.

### Option B — Quality + growth (moderate)

All Option A criteria, plus:

| Criterion | Threshold (working assumption) | Rationale |
|---|---|---|
| Trailing 3-year revenue growth | > 0% (CAGR) | Excludes shrinking businesses |
| Most recent quarter EPS growth | > -25% YoY | Excludes severely deteriorating earnings |

This is more restrictive and eliminates additional names whose revenues are in secular decline. Risk: filters out some genuine turnarounds where P&F would have caught the inflection early.

### Option C — Quality + growth + valuation (most strict)

All Option B criteria, plus:

| Criterion | Threshold (working assumption) | Rationale |
|---|---|---|
| Industry-relative P/E percentile | < 90th percentile | Excludes the most overvalued names in each industry |
| Industry-relative PEG | < 90th percentile, or N/A | Excludes overpriced-for-their-growth names |

This is the strictest of the standard options and starts to interfere with momentum names that legitimately deserve a premium. Less recommended for a P&F-primary screen — momentum is exactly what P&F detects, and momentum stocks often look expensive on fundamentals.

### Option D — Custom

Whatever criteria the advisor uses today in their manual workflow. The filter ports their existing approach into the bot. This is the right answer if the advisor has a specific fundamental screen they already trust.

---

## Recommendation

**Start with Option A** (quality gate only). Reasoning:

1. The filter's job is to remove garbage, not to pick winners.
2. Option A is narrow enough not to fight the P&F engine on legitimate turnarounds.
3. The advisor can tighten to Option B later if they find too many low-quality names slipping through.

If Option D is on the table — i.e., the advisor has an existing fundamental screen — that becomes the right answer instead. The advisor's existing judgment beats any default we'd recommend.

---

## Industry-relative thresholds

Where the filter uses metrics that vary by industry (P/E, debt/equity, ROE), the threshold should be **industry-relative**, not absolute. A debt/equity of 2.0 is alarming for a software company and fine for a utility. Implementation: compute each metric as a percentile *within the ticker's GICS industry group*, then apply the filter on the percentile.

For metrics that are scale-free (FCF positive, has-filed-recently), use absolute thresholds.

---

## Catalyst flags — additive, not subtractive

Even though the filter is binary (pass/fail), the engine also computes **catalyst flags** that don't filter but **tag** the candidate in the report. These tell the advisor about events the chart can't see:

- Upcoming earnings within N business days (default: 7)
- Most recent earnings: beat or miss
- Most recent guidance change (raised, maintained, cut)
- Recent insider buying activity (Form 4 filings — large net-buying clusters)

These flags are displayed prominently in the report next to each candidate so the advisor can weigh event risk before acting.

---

## Implementation notes

- **Data source:** Financial Modeling Prep (FMP) or SimFin for the underlying fundamentals. SEC EDGAR as the authoritative fallback when vendor data looks suspicious. See [../data-sources.md](../data-sources.md).
- **Refresh cadence:** fundamentals change quarterly. The engine refreshes them after each earnings season and re-computes the gate for the affected tickers.
- **Edge cases:** banks and insurance companies have non-standard financial statements (no traditional revenue, different debt-to-capital meanings). The filter must either special-case these sectors or exclude financials from the universe by default. Decision pending.
- **Survivorship bias:** historical backtests must use the financials as they were *known at the time*, not as they've been restated later. The data vendor must support point-in-time financials, or we accept some lookahead bias in the backtest.

---

## References

- Dorsey, *Point and Figure Charting* — his consistent thesis that supply/demand trumps fundamentals.
- Industry-standard fundamental ratio definitions: Damodaran, *Investment Valuation*, or any CFA curriculum reference.
- [Financial Modeling Prep API docs](https://site.financialmodelingprep.com/developer/docs).
- [SimFin API docs](https://simfin.com/data/access/api).
