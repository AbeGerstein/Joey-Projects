# Research: Norgate Data — Python SDK & US Stocks coverage

**Researched:** 2026-05-18
**Trigger:** Norgate was locked in as the project's sole data path ([decisions log](../01-decisions-log.md#2026-05-18--dwa-access-path-final-norgate-only-resolves-oq-002)) and the developer is starting Phase 1 build work. This doc captures every concrete SDK detail needed to wire up `src/pnf_bot/data/norgate.py` correctly.

---

## Subscription tier

**US Stocks Platinum.** Pricing $630/year (~$53/month). Includes:
- Daily OHLC for all US-listed common stocks, ETFs, and funds
- Historical data back to 1990 (some series further)
- Delisted securities — survivorship-bias-free
- Point-in-time historical index constituents (Russell 3000, S&P 500, etc.)
- GICS sector classifications
- Daily fundamentals (some) via LSEG

---

## 1. Python SDK installation

**Package:** `norgatedata` on PyPI. Install via:
```
pip install norgatedata
```

Or via the project's optional extras:
```
pip install -e .[norgate]
```

**Current version at research time:** 1.0.74 (October 2023).
**Dependencies:** pandas, numpy, requests, logbook (auto-installed).
**Python requirement:** 3.5+ (tested through 3.10; assume 3.11+ also works given general compatibility).

---

## 2. Norgate Data Updater (NDU) — required desktop application

The Python SDK is a **thin client** that reads from a local data store maintained by Norgate's desktop app, NDU. **NDU must be installed, authenticated, and running** for the SDK to return data.

- **OS support:** Windows only. macOS and Linux are not supported (community WINE/VM workarounds exist but aren't blessed by Norgate).
- **Authentication:** Subscriber login is done in the NDU GUI. There is no API key. The SDK does not need credentials passed at runtime.
- **Local data store:** Maintained at `C:\Users\<user>\.norgatedata\` (override path via `NORGATEDATA_ROOT` env var).
- **Auto-update:** NDU polls Norgate's servers in the background and pulls delta updates as published.
- **DO NOT close NDU.** It needs to keep running. Configure it to:
  - Auto-start with Windows
  - Minimize to system tray (not close to taskbar)
  - **Power management:** prevent the laptop from sleeping during update windows, or set a wake-on-timer that fires before the overnight pipeline runs

### Implication for our deployment

The advisor's Windows laptop must:
1. Have NDU installed and authenticated under his Norgate subscription
2. Be configured to keep NDU running (not closed) at all times
3. Have power settings that allow the machine to stay awake (or wake on schedule) for the overnight pipeline

These requirements are documented in our overall hosting and operations notes.

---

## 3. Data update cadence

- **"Market Close Edition" arrives ~5:00 PM New York time daily.** This is the canonical end-of-day update.
- Friday data tends to land slightly later.
- Multiple editions per day: Initial → Final. LSEG-sourced fundamentals land later in the evening.
- **Nightly delta runtime:** Typically a couple of minutes for US Stocks daily updates on a healthy machine. Initial database build (history back to 1990) can take an hour or more depending on bandwidth.

### Implication for our scheduling

The bot's analysis pipeline should run **after NDU has published the latest update**. Sensible options:

- Schedule at **7:00 PM ET** (or later) — definitely after the Market Close Edition arrives
- Or run early-morning at **3:00 AM MT** (5:00 AM ET) — well after any same-day updates
- Either way, the bot's first action should be to call `assert_data_is_fresh()` (see `src/pnf_bot/data/norgate.py`) and abort or flag the report if data is stale

Our `config.toml.example` default is **3:00 AM Mountain Time** (5:00 AM ET) which is safely after all NDU update windows.

---

## 4. Sector classification — GICS

- Norgate supports two industry classification systems: **GICS** (MSCI/S&P) and **TRBC** (Refinitiv/LSEG). Other proprietary schemes exist for non-equity assets.
- **For US equities we use GICS** — it's the industry standard and what most fundamental data vendors align to.
- **Full GICS hierarchy:** Sector (level 1) → Industry Group (level 2) → Industry (level 3) → Sub-Industry (level 4).
- **SDK functions:**
  - `norgatedata.classification(symbol, schemename='GICS', classificationresulttype='Name')` — full classification string
  - `norgatedata.classification_at_level(symbol, 'GICS', 'Name', level=N)` — specific tier (1–4)
- **Our usage:** sector = level 1 ("Information Technology"); industry = level 3 ("Technology Hardware, Storage & Peripherals"). Stored as plain strings in our Ticker table.

### Caveat — historical reassignments

Norgate's docs imply GICS is exposed as a **current-state attribute** rather than a point-in-time timeseries. If a stock's sector changed historically, our database will reflect the *current* sector for both historical and current evaluations.

For the v1 screener this is acceptable: sector mismatches at historical dates are rare and matter most for very long-horizon analyses. If it ever matters more, we'd add a sector-change-tracking job that snapshots Norgate's current sector at each daily run and tracks changes over time.

**(Item flagged in [OQ-010](../02-open-questions.md) — confirm with Norgate support whether a PIT-GICS timeseries is available before relying on the current-state assumption.)**

---

## 5. Universe construction

- `norgatedata.database_symbols('US Equities')` — returns symbols of every actively-listed US common stock
- `norgatedata.database_symbols('US Equities Delisted')` — returns delisted symbols
- Union of the two gives a **survivorship-bias-free symbol space**

For curated universes (Russell 3000, S&P 500, etc.), pre-built watchlists are available:
- `norgatedata.watchlist_symbols('Russell 3000 Current & Past')` — all members ever
- `norgatedata.watchlist_symbols('Russell 3000 Current')` — current members only

### Point-in-time index membership

For survivorship-bias-free backtesting at a specific historical date:

```python
series = nd.index_constituent_timeseries(symbol, 'Russell 3000', timeseriesformat='pandas-dataframe')
# series.index is dates; the column is 0/1 membership flag
```

This is the canonical PIT mechanism. Iterate over the union of `database_symbols('US Equities')` + `database_symbols('US Equities Delisted')`, and for each symbol check its 0/1 membership at the target date.

---

## 6. OHLC fetch

**Function:**
```python
norgatedata.price_timeseries(
    symbol,
    stock_price_adjustment_setting=norgatedata.StockPriceAdjustmentType.TOTALRETURN,
    padding_setting=norgatedata.PaddingType.NONE,
    start_date=...,
    end_date=...,
    timeseriesformat='pandas-dataframe',
)
```

**Return shape:** pandas DataFrame indexed by trade date with columns:
- `Open`, `High`, `Low`, `Close`, `Volume`, `Turnover`, `Dividend`, `Unadjusted Close`

(Our adapter normalizes these to lowercase.)

**Adjustment options:**
| `StockPriceAdjustmentType.*` | Meaning |
|---|---|
| `TOTALRETURN` (default) | Splits + dividends adjusted — **what we use for P&F** |
| `CAPITAL` | Splits + capital events; dividends NOT reinvested |
| `CAPITALSPECIAL` | Splits + special distributions |
| `NONE` | Raw unadjusted |

The `Unadjusted Close` column is always returned regardless of setting, in case it's needed for any specific calculation.

**One ticker per call.** No batch fetch. Russell 3000 typically iterates in well under a minute because the data is local.

**Corporate actions** are exposed separately via `nd.capital_event_timeseries()` and `nd.dividend_yield_timeseries()` for use cases that need to see the actions themselves.

**Padding** controls how non-trading days appear: `PaddingType.NONE` returns only trading days (what we want); `ALLMARKETDAYS`, `ALLWEEKDAYS`, `ALLCALENDARDAYS` are available for use cases that need fixed cadence.

---

## 7. Benchmark for Relative Strength — RSP recommended

DWA's documented RS methodology uses the S&P 500 Equal Weighted Index (SPXEWI).

- **RSP (Invesco S&P 500 Equal Weight ETF)** is verified-available in Norgate's coverage and tracks SPXEWI nearly perfectly. It is the safe default.
- The underlying index symbol (`$SPXEW` / `SPXEWI`) should exist on the Platinum tier but the exact Norgate-side ticker must be verified in NDU's Database tab post-subscription.

Our adapter uses `RSP` by default (`DEFAULT_BENCHMARK_SYMBOL = "RSP"` in `norgate.py`). Override via config if the index symbol turns out to be preferable.

---

## 8. Key SDK functions our adapter uses

| Function | Purpose |
|---|---|
| `database_symbols(db_name)` | enumerate universe |
| `watchlist_symbols(name)` | curated universe lists (Russell 3000, etc.) |
| `index_constituent_timeseries(symbol, index_name, ...)` | point-in-time membership |
| `security_name(symbol)` | company name |
| `exchange_name(symbol)` | listing exchange |
| `last_quoted_date(symbol)` | active vs delisted determination |
| `classification(symbol, 'GICS', 'Name')` | full GICS classification |
| `classification_at_level(symbol, 'GICS', 'Name', level=N)` | specific GICS tier |
| `price_timeseries(symbol, ...)` | OHLC fetch |
| `capital_event_timeseries(symbol)` | corporate actions |
| `dividend_yield_timeseries(symbol)` | dividend stream |

All wrapped in `src/pnf_bot/data/norgate.py`.

---

## 9. Gotchas

1. **NDU must be open.** SDK calls return stale or empty data silently if NDU is closed. Our adapter wraps every call with `NorgateNotConfiguredError` and the operator gets a clear message at the CLI level.
2. **Sleep/hibernate pauses NDU updates.** The Windows laptop needs power settings that keep it awake or wake it before the overnight job.
3. **`.norgatedata` folder must be writable.** Permissions issues there manifest as cryptic SDK errors.
4. **No graceful "is NDU running?" check** in the SDK. Our `assert_data_is_fresh()` works around this by checking the date of SPY's most recent bar.
5. **Symbols use NDU's naming convention** which is mostly the standard exchange ticker but with edge cases for share classes, REITs, etc. — verify by inspecting `security_name()` for any name where ambiguity matters.

---

## 10. Operational checklist for the advisor

When the Norgate subscription is activated, complete these steps on the laptop where the bot will run:

1. Subscribe to **US Stocks Platinum** at norgatedata.com
2. Install **Norgate Data Updater (NDU)** on the laptop
3. Sign in to NDU with the subscriber credentials
4. Let NDU complete its **initial database build** (could take 1+ hours)
5. In NDU settings:
   - Enable "Start with Windows"
   - Set "Minimize to system tray on launch"
6. In Windows power settings:
   - Disable sleep when on AC power (or schedule a wake timer for ~2:30 AM MT)
   - Disable hibernate
7. `pip install -e .[norgate]` in the bot's Python environment
8. Run `pnf-bot init-db` to create the SQLite schema
9. Run `pnf-bot refresh-universe` to populate the Ticker table
10. Run `pnf-bot backfill-prices` to load historical OHLC (depends on universe size — may take 5–30 minutes)

After step 10, the bot has a full local dataset and is ready for Phase 2 (P&F engine) work to start producing actual analysis.

---

## Sources

- [norgatedata on PyPI](https://pypi.org/project/norgatedata/)
- [Norgate Data Updater Overview](https://norgatedata.com/ndu-overview.php)
- [NDU Usage](https://norgatedata.com/ndu-usage.php)
- [NDU FAQ](https://norgatedata.com/ndu-faq.php)
- [NDU Installation](https://norgatedata.com/ndu-installation.php)
- [Stock Market Packages / Pricing](https://norgatedata.com/stockmarketpackages.php)
- [Data Content Tables](https://norgatedata.com/data-content-tables.php)
- [NDU Watchlist Library](https://norgatedata.com/ndu-watchlist-library.php)
- [Concretum: Survivorship-bias-free Norgate DB in Python](https://concretumgroup.com/how-to-construct-a-survivorship-bias-free-database-in-norgate-using-python/)
- [Price Action Lab: norgatedata unadjusted close](https://www.priceactionlab.com/Blog/2024/08/norgate-data-unadjusted-charts/)
- [AmiBroker Forum: GICS Classification in Norgate](https://forum.amibroker.com/t/gics-classification/38059)
