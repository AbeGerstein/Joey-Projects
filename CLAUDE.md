# Claude Code orientation for this repository

This file is the first thing a Claude Code session should read when opening this repository. It tells Claude what this project is, where the canonical documentation lives, and what kind of operations are common here.

---

## What this is

**PnF Bot** — an automated daily Point and Figure stock screener built for a financial advisor at a wealth management firm. The bot ingests US equities OHLC from Norgate Data, runs the full P&F methodology (chart construction, signals, RS, BPI, pre-momentum + in-momentum pattern detection), and emails a daily PDF report to the advisor at 8 AM Mountain Time.

**Status:** functionally complete as of 2026-05-18. 213 tests passing. Awaiting Norgate subscription activation on the advisor's Windows laptop for production deployment.

---

## Where to read first

If you're opening this repo for the first time, read in this order:

1. **[README.md](README.md)** — project overview, current status, doc map, hard constraints
2. **[docs/00-project-outline.md](docs/00-project-outline.md)** — phased build plan with what's done and what's pending
3. **[docs/01-decisions-log.md](docs/01-decisions-log.md)** — every material decision with date, rationale, status. Append-only audit trail.
4. **[docs/02-open-questions.md](docs/02-open-questions.md)** — anything still pending input
5. **[docs/research/norgate-data.md](docs/research/norgate-data.md)** — how the Norgate SDK works and what the bot expects from it
6. **[docs/deployment/](docs/deployment/)** — runbook, troubleshooting, maintenance, working-with-Claude

---

## Hard constraints (locked decisions)

- **Asset class:** US equities only (common stocks; ETFs/CEFs/BDCs/preferreds filtered out)
- **Direction:** long positions only (no shorts, no futures, no derivatives)
- **Audience:** the advisor only — internal idea generation; never client-facing
- **Universe filter:** all US-listed common stocks above $1 minimum price
- **Data source:** Norgate Data Platinum, US Stocks subscription
- **Benchmark:** RSP (Invesco S&P 500 Equal Weight ETF) as the verified-available proxy
- **Methodology:** P&F per Thomas J. Dorsey's *Point and Figure Charting* — **no fundamental filter**
- **Report:** daily PDF email to `Jromero816@yahoo.com` at 8:00 AM Mountain Time, subject "Daily PnF stock report"
- **Section sizes:** top 10 in Section A (pre-momentum), top 10 in Section B (in-momentum)
- **Box scaling:** Dorsey's traditional price-tiered table for price charts; percentage (6.5%) for RS charts
- **Reversal:** 3-box
- **Hosting:** advisor's Windows laptop, kept running at his office, overnight cron

---

## What this codebase looks like

```
src/pnf_bot/
├── config.py           — Pydantic config models, TOML loader
├── cli.py              — Click CLI: init-db, refresh-universe, backfill-prices, refresh-prices, daily-run, version
├── data/               — Phase 1: Norgate adapter + storage layer
│   ├── norgate.py      — all Norgate SDK interaction
│   ├── storage.py      — SQLAlchemy models (Ticker, DailyBar, SignalState, ReportArchive, LiveRecommendationRow)
│   ├── universe.py     — universe loader with common-stock filter
│   └── prices.py       — OHLC backfill + incremental refresh
├── pnf/                — Phase 2: P&F analysis engine
│   ├── types.py        — Column, PnFChart, ColumnType
│   ├── box_scaling.py  — TraditionalScaling, PercentageScaling
│   ├── chart.py        — construct_chart (high/low method)
│   ├── signals.py      — 12 signal detectors (DT/DB/TT/TB/spread/catapult/triangle/long-tail)
│   ├── trendlines.py   — 45° support/resistance lines
│   ├── rs.py           — Relative Strength chart construction
│   ├── bpi.py          — Bullish Percent Index + 6-state classifier
│   └── posture.py      — StockPosture summary record
├── scoring/            — Phase 4: pattern detection + composite scoring
│   ├── pre_momentum.py — 7 pre-momentum patterns
│   ├── in_momentum.py  — 6 in-momentum patterns
│   ├── anti_patterns.py — 4 exhaustion exclusions
│   ├── ta_composite.py — internal 0-5 TA-equivalent score
│   └── composite.py    — composite scoring + freshness multipliers + DailyReport
├── backtest/           — Phase 4D-E: backtest harness + weight tuning
│   ├── harness.py      — run_backtest
│   ├── metrics.py      — forward returns + hit rate / drawdown
│   └── tuning.py       — grid search over composite weights
├── report/             — Phase 5: rendering + delivery
│   ├── charts.py       — matplotlib PNG renderer
│   ├── detail.py       — per-stock detail compiler (15 elements)
│   ├── render.py       — Jinja2 HTML + WeasyPrint PDF
│   ├── delivery.py     — SMTP email
│   ├── audit.py        — compliance audit log
│   └── templates/      — Jinja2 .html.j2 files
└── feedback/           — Phase 6: live recommendation tracking + scoreboard
    └── tracker.py

tests/                  — 213 tests, all passing
scripts/                — end_to_end_smoke.py, send_test_email.py
docs/                   — extensive project documentation (read first!)
```

---

## Common operations

### Run the test suite
```
python -m pytest tests/
```
Expect 213 tests, all passing.

### Run lint
```
python -m ruff check src/pnf_bot tests
```
Expect "All checks passed!"

### Run the end-to-end smoke test (no Norgate needed)
```
python scripts/end_to_end_smoke.py
```
Generates a sample HTML + PDF report from synthetic data into `out/smoke/`.

### Run the bot for real (Norgate must be active)
```
pnf-bot daily-run
```
Requires `config.toml` filled in and NDU running.

---

## How to extend or fix

When you need to make a code change:
1. Make the change in `src/pnf_bot/...`
2. Add a test in `tests/` if it's behavioral
3. Run `python -m pytest tests/` to verify
4. Update relevant docs in `docs/` if methodology or behavior changed
5. Add an entry to `docs/01-decisions-log.md` if it's a material decision
6. Commit and push — see [docs/deployment/working-with-claude.md](docs/deployment/working-with-claude.md) for the cross-environment workflow

---

## Things to NOT do

- **Don't scrape DWA's web platforms** (nasdaqdorseywright.com etc.) — explicit ToS violation. See [docs/research/dwa-access.md](docs/research/dwa-access.md).
- **Don't change the compliance scope** (internal-only, no client-facing output, no trade execution) without rebooting the compliance conversation. See [docs/compliance.md](docs/compliance.md).
- **Don't reintroduce a fundamental filter** — removed deliberately on 2026-05-16 per advisor direction. See the decision log.
- **Don't commit `config.toml`, real credentials, or anything in `out/` or `data/`** — covered by `.gitignore`.

---

## Project conventions

- Python 3.11+ (uses `tomllib`, modern type hints, `datetime.UTC`)
- Decimal arithmetic everywhere prices are involved
- Frozen dataclasses for value types
- Pydantic v2 models for config
- SQLAlchemy 2.x with the new typed mapped_column API
- Click for CLI
- Ruff for lint, mypy for types (mypy not in CI yet but pyproject is configured for it)
- pytest for tests
- Conventional commit-style messages (the recent history shows the style)
