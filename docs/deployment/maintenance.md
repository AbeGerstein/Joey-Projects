# Ongoing maintenance — weekly, monthly, quarterly tasks

The bot is designed to run unattended after deployment. But a few periodic operations keep it calibrated and surfaceable. This document lists them on a schedule.

---

## Every day (automatic)

The Windows Task Scheduler runs `pnf-bot daily-run` at 3:00 AM Mountain Time. You don't need to do anything. The report arrives at the advisor's inbox shortly after.

What you **should** do daily, taking ~30 seconds:
- Verify the report arrived in `Jromero816@yahoo.com` (or whatever email is configured)
- If it didn't arrive by 9 AM MT, check the audit log for a failed delivery

## Every week (manual, ~10 minutes)

### 1. Update forward returns for live recommendations

Run this once a week to back-populate the 1m / 3m / 6m / 12m return columns on past recommendations. Without this, the scoreboard stays empty.

From the bot directory (with venv active):
```
python -c "
from datetime import date
from pnf_bot.config import load_config
from pnf_bot.data import norgate
from pnf_bot.feedback import update_forward_returns

cfg = load_config('config.toml')

# Build a dict of {symbol: OHLC} for every symbol that has live recommendations
import sqlite3
conn = sqlite3.connect(cfg.data.db_path)
symbols = set(row[0] for row in conn.execute('SELECT DISTINCT symbol FROM live_recommendations'))
conn.close()

universe = {s: norgate.fetch_ohlc(s) for s in symbols}
n = update_forward_returns(cfg.data.db_path, universe)
print(f'Updated {n} forward-return cells')
"
```

This iterates over every live recommendation row that has a null forward-return column and fills it in from current OHLC. It's idempotent — runs that produce 0 updates are fine.

### 2. Verify yesterday's report arrived (if you haven't been checking daily)

Spot-check the recent audit log:
```
python -c "
from pnf_bot.data import storage
from sqlalchemy import select
with storage.get_session('data/pnf_bot.db') as s:
    rows = s.execute(select(storage.ReportArchive).order_by(storage.ReportArchive.id.desc()).limit(10)).scalars().all()
    for r in rows:
        print(r.generated_at, r.report_date, r.delivery_status, '/', r.candidate_count_section_a, '+', r.candidate_count_section_b)
"
```

You should see 5–7 rows from the past week (weekdays only; the bot still runs on weekends but markets are closed so the data is stale).

Any `delivery_status = 'failed'` rows need investigation. Look at `delivery_error` for the SMTP error.

### 3. Spot-check the bot's output against the advisor's manual reads

Pick 2–3 names the advisor would normally consider strong. Run them through the bot's chart rendering and verify the chart looks like what he sees in the DWA platform. Catches drift in the engine vs DWA conventions early.

---

## Every month (manual, ~30 minutes)

### 1. Run the scoreboard

After enough live recommendations have aged through the 1m horizon (~21 trading days = ~1 calendar month), the scoreboard becomes meaningful.

```
python -c "
from datetime import date, timedelta
from pnf_bot.config import load_config
from pnf_bot.feedback import compute_scoreboard

cfg = load_config('config.toml')
today = date.today()
sb = compute_scoreboard(cfg.data.db_path, today - timedelta(days=90), today)

print(f'Scoreboard ({sb.start_date} → {sb.end_date}, section: {sb.section})')
print(f'Total recommendations: {sb.total_recommendations}')
for h in sb.horizons:
    if h.n_picks == 0:
        continue
    print(f'  {h.horizon_label}: n={h.n_picks}, hit_rate={h.hit_rate:.1%}, '
          f'avg_winner={h.avg_winner:+.2%}, avg_loser={h.avg_loser:+.2%}, '
          f'avg_return={h.avg_return:+.2%}')
"
```

Look for:
- **Hit rate > 50%** at the 1m and 3m horizons → bot has real predictive value
- **Avg return positive** at 3m+ → setups are translating to returns
- **Avg winner / avg loser > 1.5** → asymmetric payoff (winners bigger than losers)

If these are persistently bad over several months, the methodology may need retuning (or the patterns aren't suited to the current market regime). Consider re-running weight tuning.

### 2. Review the audit log size

```
python -c "
from pathlib import Path
archive_dir = Path('reports/archive')
total = sum(f.stat().st_size for f in archive_dir.glob('*'))
print(f'Audit log: {total / 1024 / 1024:.1f} MB across {len(list(archive_dir.glob(\"*\")))} files')
"
```

If it's growing to >5GB, talk to the advisor about archiving older files to a separate location (but keep them retrievable for compliance).

### 3. Check disk space on the laptop

```
python -c "
import shutil
total, used, free = shutil.disk_usage('.')
print(f'Disk: {free / 1024**3:.1f} GB free of {total / 1024**3:.1f} GB total')
"
```

If free space is dropping below 20%, plan for cleanup (move audit logs, archive old logs, etc.).

---

## Every quarter (manual, ~1–2 hours)

### 1. Re-tune composite weights

After 3+ months of live recommendations, the live scoreboard provides real performance data. If live performance is significantly worse than the original backtest's expectations, re-tune.

```
# Build a fresh backtest config from the most recent year
from datetime import date, timedelta
from pnf_bot.backtest import BacktestConfig, WeightSearchSpec, tune_weights
from pnf_bot.data import norgate, storage
from pnf_bot.config import load_config

cfg = load_config('config.toml')

# Define rebalance dates — say, first day of each week for the past year
today = date.today()
rebalance_dates = tuple(today - timedelta(weeks=i) for i in range(52))

# Pull OHLC for the universe
# ... [build universe_ohlc dict from Norgate] ...

backtest_config = BacktestConfig(
    rebalance_dates=rebalance_dates,
    section_a_top_n=10,
    section_b_top_n=10,
)

result = tune_weights(
    backtest_config=backtest_config,
    universe_ohlc=universe_ohlc,
    benchmark_ohlc=norgate.fetch_benchmark_ohlc(),
    section='pre_momentum',
    search_spec=WeightSearchSpec(),
    test_fraction=0.2,
)

print('Best weights:', result.best.weights)
print('Train objective:', result.best.objective_value)
print('Test objective:', result.out_of_sample.objective_value if result.out_of_sample else 'N/A')
```

If the tuned weights significantly outperform the defaults on the held-out test set, update the bot's default weights. Otherwise leave them alone — over-tuning to noise is a real risk.

### 2. Review compliance posture

Walk through `docs/compliance.md`. Verify:
- The bot still operates strictly internally (no client-facing material has been added)
- The disclaimer is still present on every report (open a recent archived PDF and look)
- The audit log is being preserved for the 5–7 year window the compliance doc specifies
- Nothing about the advisor's workflow has changed that would expand scope

### 3. Verify Norgate subscription is current

Norgate billing renews annually. Make sure the subscription hasn't lapsed (NDU will start showing errors if it has). Renewal usually happens automatically via the credit card on file.

---

## Every year (manual, ~half a day)

### 1. Update Python and dependencies

Newer versions of pandas, numpy, sqlalchemy may have security fixes or performance improvements. Test in a separate venv first:

```
python -m venv .venv-test
.venv-test\Scripts\activate
pip install -e .[norgate,dev] --upgrade
python -m pytest tests/
```

If all 213 tests still pass, swap the active venv. If anything breaks, investigate before upgrading the production venv.

### 2. Renew Gmail app password (optional)

App passwords don't expire, but rotating them yearly is good security hygiene. Generate a new one, update `config.toml`, restart the scheduled task.

### 3. Annual compliance review

Schedule a meeting with the firm's compliance officer (if any). Review:
- What the bot has been doing this year
- Any near-misses or oddities the audit log shows
- Whether the firm's policies have changed in ways that affect scope
- Whether the recordkeeping retention period has changed
