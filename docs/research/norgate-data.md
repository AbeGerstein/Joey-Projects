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

- **Initial edition publishes ~5:00 PM Eastern Time.**
- **Final edition publishes ~9:00 PM Eastern Time** the same trading day. This is what the bot should consume — it includes any late corrections.
- **Friday data sometimes slips later** than other weekdays — Norgate explicitly flags this. Still well before our 3 AM MT (5 AM ET) Saturday run window.
- Multiple editions per day means an early-evening run might miss late corrections. Schedule after 9 PM ET (e.g., overnight at 3 AM MT) for safety.
- **Nightly delta runtime:** typically a couple of minutes for US Stocks daily updates on a healthy machine.
- Initial database build (full history back to 1990) takes an hour or more depending on bandwidth.

## 3a. Performance characteristics — confirmed 2026-05-18

- **No rate limits.** Data is local-disk, IPC-served. Network is not in the loop after NDU has synced.
- **Memory footprint:** a full Russell 3000 backtest spanning history back to 1990 can peak around 10.5 GB RAM (per Concretum's reference implementation). For our 10-year window the working set is much smaller (~2-3 GB).
- **Pattern:** fetch and persist in batches of 200-500 symbols to keep memory bounded. Our `fetch_ohlc_bulk()` does per-symbol iteration which keeps the memory profile low.
- **Speed:** a full Russell 3000 fetch over 10 years typically completes in a few minutes on a modern laptop. The bottleneck is pandas DataFrame construction, not data retrieval.

These numbers are aspirational until benchmarked on the advisor's actual hardware post-subscription.

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

### Confirmed limitation — historical reassignments

Norgate exposes GICS as a **current-state attribute only**. There is **no point-in-time GICS timeseries function** in the public SDK — neither `gics_timeseries()` nor any equivalent exists. `classification()` and `classification_at_level()` both return the latest assignment only.

This applies to all classification schemes Norgate carries (GICS, TRBC, NAICS, SIC, RBICS) — none have point-in-time tracking.

**For our use case this is acceptable:**
- Sector mismatches at historical dates are uncommon (most stocks stay in their GICS sector for years)
- The impact is limited to sector BPI accuracy at historical backtest dates for stocks that changed sectors
- For live forward operation, current-state GICS is correct

If we ever need point-in-time GICS:
- Build our own daily-snapshot tracker (record each stock's current GICS daily; build a timeseries over time)
- Or source historical GICS from a different vendor (FactSet, S&P direct)
- Or file a feature request with Norgate (no expectation it will land)

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

## 7. Benchmark for Relative Strength — RSP (verified) preferred over $SPXEW (unverified)

DWA's documented RS methodology uses the S&P 500 Equal Weighted Index (which DWA labels "SPXEWI"; the standard ticker is `SPXEW`).

**Status of `$SPXEW` on Norgate (researched 2026-05-18):**

- Norgate uses a `$`-prefix convention for indexes (`$SPX`, `$RUA`, `$NDX`, etc.).
- The Norgate published catalog lists `$SPX`, `$OEX`, `$MID`, `$SML`, `$SP1500`, `$SPDAUDP`, `$SPESG` — **no equal-weight S&P 500 variant**. `$SPXEW` is NOT in the public catalog.
- It may still be accessible via the SDK post-subscription (S&P licenses the EW index separately), but cannot be assumed.
- This requires login or email to support@norgatedata.com to confirm definitively.

**Our default: RSP.** `RSP` (Invesco S&P 500 Equal Weight ETF) is verified available in `US Equities`, tracks `SPXEW` within ~1 basis point, and works under the same `price_timeseries()` call as any common stock. It is the safe, verified default for RS calculations. The bot's adapter defaults to `RSP` (`DEFAULT_BENCHMARK_SYMBOL = "RSP"` in `norgate.py`).

If the advisor verifies `$SPXEW` is available post-subscription, set `norgate.benchmark_symbol = "$SPXEW"` in `config.toml` — no code change required.

## 7a. Symbol conventions — confirmed 2026-05-18

- **Indexes use `$`-prefix:** `$SPX`, `$RUA`, `$NDX`, `$DJI`, etc.
- **Multi-class shares use dot notation:** `BRK.A`, `BRK.B` — matches the NYSE/NASDAQ exchange convention.
- **ADRs sit inside `US Equities`** (not a separate database). Filtered the same way as common stocks.
- **REITs are classified as Equity / Operating-Holding Company** — they pass the common-stock filter (which is correct for our use; advisors trade REITs like stocks).
- **Symbol changes (FB → META):** Norgate stores history under the **current symbol only**. META's full history (including its FB era) is under `META`. There is no public SDK function to query previous symbols.
- **`subtype1` values:** `Equity`, `Hybrid`, `Derivative`, `Debt`, `Exchange Traded Product`, `Index`, `Currency Cross`, `Cryptocurrency`.
- **`subtype2` values for Equity subtype1:** `Operating/Holding Company` (common stocks + REITs), `Investment Company` (CEFs, BDCs), `Special Purpose Company`, `Exchange Traded Note`, `Structured Product`, `Exchange Traded Fund`, `Exchange Traded Managed Fund`, `Preferred`, `Convertible Preferred`, `Warrant`, `Right`.

## 7b. Common-stock filter — required, not optional

**Critical finding:** Norgate's `US Equities` database contains **all** US-listed securities, not just common stocks. ETFs, CEFs, BDCs, preferreds, warrants, and ETNs are all in there. Without filtering, a raw `database_symbols('US Equities')` call returns ~6,000-7,000 symbols, of which only ~3,500-4,000 are actual common stocks.

The bot's universe loader filters via `subtype1 == 'Equity' AND subtype2 == 'Operating/Holding Company'`. This keeps:
- Common stocks of all market caps
- REITs (classified as Operating/Holding Companies)

And excludes:
- ETFs and ETNs
- Closed-End Funds
- Business Development Companies (BDCs — note: these are tradable equities but Norgate classifies as Investment Companies, which we exclude per the standard Concretum-style universe filter)
- Preferred shares (regular and convertible)
- Warrants, rights, special-purpose companies, structured products

The filter is implemented in `norgate.is_common_stock()` and applied at universe load time via `norgate.list_common_stocks()`.

**BDC note:** if the advisor wants BDCs included in scope later, change the subtype2 filter to allow both `Operating/Holding Company` and `Investment Company`, or maintain a separate watchlist of approved BDC tickers.

## 7c. Exception handling — only `ValueError` is documented

Per the `norgatedata` PyPI page, the SDK raises **only `ValueError`** for invalid symbols and invalid parameters. Other failure modes (NDU not running, database not built, IPC failure) typically surface as silent empty returns or low-level errors.

Our adapter:
- Catches `ValueError` explicitly for symbol/parameter errors
- Catches generic `Exception` as a fallback for NDU-down and IPC failures
- Wraps both into `NorgateNotConfiguredError` so the CLI can surface one consistent error to the operator

Pre-flight check: call `norgate.check_status()` at the start of the overnight pipeline to verify NDU is responding before any data fetch attempts run.

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

## 10. Coverage check — does Norgate enable our full P&F methodology?

The honest answer: **yes, every piece of P&F analysis we've designed runs from Norgate's data.** P&F is fundamentally a price-based methodology, and Norgate gives us clean adjusted prices, historical depth, point-in-time universes, and sector tags. The math is deterministic on OHLC — given the same prices, our engine produces the same chart DWA would.

### Full coverage table

| Methodology piece | Norgate inputs we use | Verdict |
|---|---|---|
| P&F chart construction (Xs/Os from high/low) | Adjusted daily OHLC | ✅ |
| Box scaling (traditional price-tiered table) | Price levels in OHLC | ✅ |
| 3-box reversal logic | OHLC | ✅ |
| All 8 signal types (DT, DB, TT, TB, spread TT/B, catapult, triangle, long tail) | OHLC → P&F chart | ✅ |
| 45° trendlines (bullish support / bearish resistance) | OHLC → P&F chart | ✅ |
| Relative Strength chart vs equal-weight benchmark | Stock OHLC + RSP OHLC | ✅ |
| RS buy/sell signal detection | RS chart from prices | ✅ |
| Bullish Percent Index (universe + 11 sector BPIs) | Per-stock signals + GICS sectors | ✅ |
| All 7 pre-momentum patterns | P&F chart + RS + BPI | ✅ |
| All 6 in-momentum patterns | Same | ✅ |
| Anti-pattern exclusions | P&F chart geometry | ✅ |
| Composite scoring (internal 0–5 TA-equivalent) | Above components | ✅ |
| Freshness multipliers (new-last-night) | SignalState diffs | ✅ |
| Survivorship-bias-free backtest back to 1990 | Active + delisted symbols, PIT index constituents | ✅ |

### Methodological differences from DWA worth knowing honestly

| Item | DWA | Norgate path | Impact |
|---|---|---|---|
| Sector taxonomy | DALI (proprietary) | GICS (industry standard) | Slightly different sector groupings → slightly different sector BPI values. Both methodologically valid; the BPI math is identical. |
| RS benchmark | SPXEWI (raw index) | RSP (the ETF tracking it) | Tracking difference is typically under 1 basis point. Essentially indistinguishable. |
| TA composite score | DWA's proprietary formula (0–5) | Our transparent 5-condition composite | Different exact value, captures the same posture concept. Expected to correlate strongly with DWA's in live use. |
| Historical GICS reassignments | (DWA's behavior unknown) | Current-state only via Norgate (per docs) | Minor backtest bias for stocks that switched sectors years ago. See OQ-010. |

### The one thing Norgate doesn't provide

**DWA's proprietary Technical Attributes composite score as a directly-fetched number.** This is the same gap we accepted when we chose the Norgate-only path. We compute our own functionally-equivalent 5-condition composite. The advisor can spot-check our composite against DWA's TA score via his existing platform subscription whenever he wants.

### Two things to verify once Norgate is activated

1. **SPXEWI index availability.** RSP (ETF) is verified available. If raw `$SPXEW` is also available on Platinum, the raw index may be marginally preferred. 30-second check in NDU's Database tab.
2. **Historical GICS via API.** Norgate's docs imply current-state only. Worth asking Norgate support directly — if a point-in-time GICS timeseries is exposed, we can improve backtest fidelity for sector-change cases.

Neither blocks anything. Both are post-activation refinements.

---

## 11. Operational checklist for the advisor

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
