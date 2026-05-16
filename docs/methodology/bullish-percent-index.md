# Methodology: Bullish Percent Index (BPI)

The Bullish Percent Index is a market-breadth indicator and one of the most distinctive tools in the Dorsey Wright methodology. While P&F charts tell you what an individual stock is doing, the BPI tells you what *the market as a whole* (or a specific sector) is doing — and crucially, it tells you whether the offense should be on the field or the defense.

This document follows the BPI definition and interpretation framework from Dorsey's *Point and Figure Charting*.

---

## Definition

The BPI for any universe of stocks is simply:

```
BPI = (Number of stocks currently on a P&F buy signal / Total number of stocks in the universe) × 100
```

It is a percentage, ranging from 0 (every stock in the universe is on a sell signal) to 100 (every stock is on a buy signal).

The BPI itself is plotted as a **P&F chart** with:

| Parameter | Value |
|---|---|
| Box size | 2% (i.e., each box represents a 2-percentage-point change) |
| Reversal | 3-box |
| Axis | 0% to 100% |

Because the BPI is a percentage, this is one of the few cases in Dorsey's framework where the chart construction itself uses percentage thinking — but the box size is *additive* (2 percentage points), not multiplicative.

---

## Universes

A BPI exists for any defined universe. The classic ones:

| BPI | Universe |
|---|---|
| **NYSE BPI** | All NYSE-listed common stocks |
| **NASDAQ BPI** | All NASDAQ-listed common stocks |
| **OTC BPI** | OTC-listed stocks |
| **Sector BPIs** | Each major industry sector (e.g., Technology BPI, Energy BPI, Financials BPI) |

In this project we'll compute BPIs for:

- **Our screening universe BPI** (Russell 3000 or whatever is locked in [OQ-003](../02-open-questions.md))
- **Sector BPIs** for the 11 GICS sectors covering that universe

DWA's sector definitions don't perfectly match GICS, but GICS is close enough for v1 and is the only sector taxonomy widely available from data vendors.

---

## The six market states

Dorsey identifies six distinct postures the BPI can be in. These are the key interpretive framework — the BPI's *level* matters less than its *current column direction* and the *region* it's in.

| State | Description | Posture |
|---|---|---|
| **Bull Confirmed** | BPI is in a column of X's (rising) and above its most recent bear signal | Offense — most aggressive long-favorable state |
| **Bull Correction** | BPI was in Bull Confirmed but has reversed into a column of O's | Caution — bulls still in control but a pullback is underway |
| **Bull Alert** | BPI was below 30% and has reversed up into a column of X's | Early offense — historically a powerful long signal |
| **Bear Confirmed** | BPI is in a column of O's (falling) and below its most recent bull signal | Defense — most aggressive bearish state |
| **Bear Correction** | BPI was in Bear Confirmed but has reversed into a column of X's | Caution — bears still in control but a bounce is underway |
| **Bear Alert** | BPI was above 70% and has reversed down into a column of O's | Early defense — historically a powerful exit/short signal |

The states above 70% (**high-risk zones**) and below 30% (**high-reward zones**) carry extra weight. Dorsey's rule of thumb:

> "When the BPI is above 70%, the market is overbought — be defensive. When it's below 30%, the market is oversold — be opportunistic."

---

## How BPI is used in this project

The bot uses the BPI framework in three places:

### 1. Overall market posture
The screen-universe BPI's current state is a top-of-report element. When the BPI is in a bullish state, the bot operates normally. When the BPI is in a bearish state, the bot still surfaces the strongest candidates but flags the macro headwind prominently in the report.

This does *not* mean stop screening when the market is bearish — bear-market leaders are real and identifiable. It means **contextualize**: the same setup is higher-conviction in a Bull Confirmed market than in Bear Confirmed.

### 2. Sector tailwind input to the composite score
Each candidate's sector BPI feeds into its composite score. Candidates in sectors that are in Bull Confirmed or Bull Alert states get a positive contribution; candidates in Bear Confirmed sectors get a negative contribution. This implements the "sector rotation" lens that's central to DWA's framework.

### 3. Risk gates
Optional risk gates the advisor may want:
- *Skip the day's screen entirely* when the universe BPI enters Bear Confirmed (controversial — see note below)
- *Reduce position-size guidance* in the report when the BPI is above 70%
- *Increase signal-strictness* (fewer but higher-quality candidates) in Bear Confirmed regimes

We will not implement risk gates by default; they would be opt-in flags the advisor sets if desired.

---

## A note on edge cases

- **Defining "on a buy signal."** A stock is on a buy signal between the time its most recent signal was a buy (double top, triple top, catapult, etc.) and the time its next sell signal fires. This is a stateful classification — the engine must track each stock's signal-state-as-of-date, not just the most recent column.
- **New listings.** Stocks with insufficient history for a meaningful P&F chart should be excluded from BPI computation. Apply the same minimum-history filter used elsewhere in the project (e.g., 6 months of price data).
- **Delistings and corporate actions.** When a stock leaves the universe (delisted, acquired), it stops contributing to the BPI. Don't carry forward stale signals.
- **Universe drift over time.** For a faithful historical BPI series, the universe must be point-in-time accurate — Russell 3000 constituents change every year. The data vendor must provide historical constituents, or we accept some survivorship bias. (See [OQ-007](../02-open-questions.md#oq-007-backtest-universe-and-look-back-window).)

---

## Implementation notes

- BPI is computed every trading day from the up-to-date signal state of every stock in the universe.
- The engine must compute a full historical BPI series (years of daily values) to support backtesting and to plot the BPI itself as a P&F chart.
- Sector BPIs are computed identically, just over sector subsets of the universe. For a Russell 3000 universe with GICS sector tags, this is 11 additional BPI series — cheap.
- The "BPI as a P&F chart" is itself a P&F chart with 2% boxes. The engine reuses its standard P&F construction logic with the percentage-box mode.

---

## References

- Dorsey, *Point and Figure Charting*, the BPI chapter — definitive treatment of the six market states.
- DWA platform documentation on Bullish Percent indicators (accessible via the advisor's NDW subscription).
- StockCharts and other independent sources document the BPI methodology faithfully — useful for cross-checking the implementation.
