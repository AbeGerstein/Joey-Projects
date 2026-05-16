# Methodology: Point and Figure Charting

This document is the working reference for how P&F charts are constructed and interpreted in this project. All definitions and rules here follow **Thomas J. Dorsey, *Point and Figure Charting*** — that book is the canonical source. When this document is silent or ambiguous on a point, the book wins.

---

## What a P&F chart is

A P&F chart records only meaningful price changes, ignoring time and volume. Columns of **X's** represent rising prices, columns of **O's** represent falling prices. Each X or O occupies one box on the chart; a box is a fixed price increment determined by the scaling rules below. A new box is added to a column only when price moves by at least one full box's worth in the prevailing direction. The column reverses (X → O or O → X) only when price moves at least three boxes against the prevailing direction — this is the **3-box reversal** convention used throughout this project.

The result is a chart that filters out short-term noise and emphasizes net supply and demand. Time appears only implicitly: a single column can span many days or weeks; a single day can produce no plot change at all.

---

## Box scaling

The size of one box depends on the price of the security being charted. We use two scaling modes:

### Traditional scaling (price charts — Dorsey's default)

This is the standard table from *Point and Figure Charting*. Use this for all stock price charts:

| Price range | Box size |
|---|---|
| Under $5.00 | $0.25 |
| $5.00 – $20.00 | $0.50 |
| $20.00 – $100.00 | $1.00 |
| $100.00 – $200.00 | $2.00 |
| $200.00 – $500.00 | $4.00 |
| $500.00 – $1,000.00 | $5.00 |
| Over $1,000.00 | $10.00 |

**Combined with 3-box reversal:** a $50 stock has $1 boxes, so a column reversal requires a $3 move against the trend. A $250 stock has $4 boxes, so reversal requires a $12 move.

### Percentage scaling (RS charts and high-priced indexes)

Each box is a fixed percentage of price. Used for **Relative Strength charts** (see [relative-strength.md](relative-strength.md)) and for charting very-high-priced indexes where traditional scaling becomes coarse.

| Use case | Box size |
|---|---|
| Stock RS chart | 6.5% |
| Fund RS chart | 3.25% |

The reversal rule is still 3 boxes — but each box is multiplicative rather than additive, so the chart compounds proportionally with price.

---

## Chart construction algorithm (high/low method)

Dorsey's preferred method uses each day's high and low (not just the close). Algorithm in plain English:

1. **Initialize**: pick a starting column type (X if today's range is up vs. yesterday, O if down) and plot one box at today's appropriate level.
2. **For each subsequent day**, check the current column's direction:
   - **If in an X column** (uptrend):
     - If today's **high** is at least one box above the current top of the column, extend the X column up to whatever box level today's high reaches.
     - Otherwise, if today's **low** is at least **3 box-sizes below the top of the X column**, reverse: move one column to the right and plot O's from one box below the X-column top down to today's low.
     - If neither condition is met, the chart is unchanged today.
   - **If in an O column** (downtrend):
     - If today's **low** is at least one box below the current bottom of the column, extend the O column down to whatever box level today's low reaches.
     - Otherwise, if today's **high** is at least **3 box-sizes above the bottom of the O column**, reverse: move one column to the right and plot X's from one box above the O-column bottom up to today's high.
     - If neither condition is met, the chart is unchanged today.

When in doubt about a day that *could* both extend the current column and trigger a reversal (rare), Dorsey's rule is: extend the current column first; only consider reversal if extension is not possible.

The chart can also be constructed from closes only ("close-only method"). We default to high/low because it captures intraday excursions that often produce real signals. The choice is documented as part of the engine's configuration.

---

## Signals — buy and sell

A signal is what makes a P&F chart actionable. The signal fires on the box where price *exceeds* a prior reference level, not when it merely touches it. All signals below assume 3-box reversal.

### Foundational signals

| Signal | Bullish/Bearish | Definition |
|---|---|---|
| **Double Top** | Bullish | The current X column rises one box above the top of the immediately preceding X column. |
| **Double Bottom** | Bearish | The current O column falls one box below the bottom of the immediately preceding O column. |

These are the most common P&F signals. The double top is the basic buy signal; the double bottom is the basic sell signal.

### Stronger continuation signals

| Signal | Bullish/Bearish | Definition |
|---|---|---|
| **Triple Top** | Bullish | The current X column exceeds the tops of two prior X columns at the same level. |
| **Triple Bottom** | Bearish | The current O column drops below the bottoms of two prior O columns at the same level. |
| **Spread Triple Top** | Bullish | Three prior X columns hit highs at *similar but not identical* levels, and the current X column exceeds all of them. |
| **Spread Triple Bottom** | Bearish | Mirror of the above. |
| **Bullish Catapult** | Bullish | A triple top followed by a pullback (one O column) and then a double top breakout. Considered a high-conviction setup. |
| **Bearish Catapult** | Bearish | Mirror of the above. |

### Pattern signals

| Signal | Bullish/Bearish | Definition |
|---|---|---|
| **Bullish Triangle** | Bullish | A coiling pattern of progressively higher lows and progressively lower highs, broken to the upside via a double top. |
| **Bearish Triangle** | Bearish | Mirror — coiling pattern broken to the downside. |
| **Long Tail Down** | Bullish reversal | An unusually long single O column (often 20+ boxes) — a capitulation signal that often precedes a bottom. |
| **Pole pattern (bullish)** | Bullish | A long X column up, a sharp pullback retracing roughly half of it, and resumption — a sign of strong demand absorbing supply. |

A full taxonomy and chart examples for each signal live in chapters 4–6 of Dorsey's book. When implementing, port the book's exact box-counting definitions into the detector functions.

---

## Trendlines (45° lines)

P&F trendlines are drawn at a fixed 45° slope (one box per column) rather than fitted to highs and lows the way bar-chart trendlines are. There are two:

### Bullish support line
Drawn upward at 45° from the **lowest O** of a chart's most recent significant decline. Stays in force as long as price (the column of X's or O's) remains above it. A break below the bullish support line is a major bearish event — often more important than a single sell signal.

### Bearish resistance line
Drawn downward at 45° from the **highest X** of a chart's most recent significant rally. Stays in force as long as price remains below it. A break above the bearish resistance line is the corresponding bullish event.

In Dorsey's framework, **a stock is considered to be in a positive trend if its price is above the bullish support line and on a buy signal**. The combination of trend posture and signal posture forms the basis of the "trend chart" classification used in many DWA workflows.

---

## Putting it together — chart classification

For each ticker, the engine produces a structured classification along several dimensions:

| Dimension | Possible values |
|---|---|
| **Trend** | Positive trend (above bullish support) / Negative trend (below bearish resistance) |
| **Most recent signal** | Specific signal name, with date and price level |
| **Current signal posture** | On a buy signal / On a sell signal |
| **Distance to next signal** | Number of boxes (and price) needed to fire the next buy or sell signal — the key pre-breakout input |
| **Pattern context** | Coiling, breaking out, extended, etc. |
| **Relative strength state** | See [relative-strength.md](relative-strength.md) |

This classification is the technical input to the combined scoring layer in Phase 4 (see [../00-project-outline.md](../00-project-outline.md)).

---

## Implementation notes

- **No production-grade Python library** implements Dorsey's conventions correctly. We build the engine from scratch. A handful of libraries exist (`pypf`, scattered Jupyter notebooks) but they make different scaling and reversal choices and don't implement the full signal set.
- **Test fixtures should come from the book.** Many of Dorsey's chapters include worked examples with the resulting chart fully drawn out — those are gold for unit tests.
- **Cross-validation against the DWA platform** (if the manual-CSV-export path is chosen) is the strongest validation. The advisor can pull a few charts from the platform and we compare ours to theirs.
- **Box sizing edge case:** when a stock crosses a price-tier boundary (e.g., a $98 stock rallies to $105), Dorsey's rule is to keep the existing box size until a new column begins, then re-evaluate. The engine must encode this; otherwise charts will "rescale" mid-column and produce nonsense.

---

## References

- Dorsey, Thomas J. *Point and Figure Charting: The Essential Application for Forecasting and Tracking Market Prices* (4th edition). Chapters 2–6 cover everything in this document; chapters 7+ cover RS, BPI, and sector rotation (separate methodology docs).
- DWA platform help articles on chart construction and signal definitions (accessible via the advisor's NDW subscription).
