# Tech Stack

This document captures the technical choices for the project and the reasoning behind each. Choices flagged "v1" are the starting point; some may be revisited in later phases as the project's needs become clearer.

---

## Language: Python (v1, likely permanent)

Python is the obvious choice for this project. Reasons:

- The financial-data ecosystem (pandas, numpy, the vendor SDKs) is Python-native.
- The data volumes are modest (a Russell 3000 universe over 20 years is tens of millions of rows — well within pandas territory).
- The team is one developer; Python's iteration speed matters more than raw runtime performance.

Version target: Python 3.11+ (modern type hints, pattern matching where useful, performance improvements).

---

## Core libraries

| Library | Purpose | Notes |
|---|---|---|
| **pandas** | Tabular data manipulation, time-series operations | Workhorse for everything |
| **numpy** | Numerical operations | Lower-level vectorization where pandas overhead matters |
| **requests** or **httpx** | HTTP client for vendor APIs | httpx if we want async; requests is simpler for synchronous flows |
| **pydantic** | Data validation for vendor responses, config models | Catches schema drift in API responses early |
| **sqlalchemy** | ORM / query builder for the local database | Lets us swap SQLite → Postgres without rewrites |
| **pytest** | Test framework | Standard |
| **ruff** | Linter + formatter | Modern, fast, replaces flake8/black for most needs |
| **mypy** | Static type checker | Worth it for a codebase that will live a long time |

---

## P&F engine: custom implementation

There is no production-grade Python library for P&F charting that follows Dorsey's conventions faithfully. Options surveyed:

| Library | Verdict |
|---|---|
| `pypf` (PyPI) | Outdated; opinionated scaling that doesn't match Dorsey's table |
| Various Jupyter notebooks | Hobbyist; not robust for production |
| `mplfinance` | Has a P&F mode but it's stylistic, not algorithmic — doesn't expose signals or trendlines as data |

We will write the P&F engine from scratch. This is significant work but the methodology is bounded and well-specified — see [methodology/point-and-figure.md](methodology/point-and-figure.md). Building it ourselves gives us:

- Faithful adherence to Dorsey's rules
- Full inspectability — every signal can be explained to the advisor
- Unit testability against book examples

The engine will live in its own module (working name `pnf/`) with clean separation between:
- Chart construction (OHLC → column data)
- Signal detection (column data → signal events)
- Trendline computation
- Classification (current state summary for a ticker)

---

## Storage

### v1: SQLite

| Aspect | Detail |
|---|---|
| **Why** | Zero-ops, file-based, perfect for a single-machine tool. Tens of millions of rows are well within its envelope. |
| **Schema scope** | Tickers table, daily OHLC table, daily fundamentals table, daily signal-state table, reports archive table |
| **Driver** | `sqlite3` (stdlib) wrapped by SQLAlchemy |

### v2 if needed: Postgres + TimescaleDB

If the universe grows much beyond Russell 3000 or if we add intraday data, Postgres with the TimescaleDB extension is the natural next step. TimescaleDB's hypertables make daily-bar storage and queries very fast.

The data layer is built behind a thin abstraction so this migration is mechanical when (if) it happens.

---

## Scheduling

### v1: cron on the host VM

The bot runs once a day after market close (e.g., 7 PM Eastern). A simple cron entry kicks off the nightly pipeline: refresh data, run the screen, generate the report, email it.

```
0 23 * * 1-5  cd /opt/pnf-bot && /opt/pnf-bot/.venv/bin/python -m pnf_bot.daily
```

(Times shown are UTC for an eastern-US deployment; adjust to the actual host TZ.)

### Alternative: GitHub Actions

If we want to avoid running our own host, GitHub Actions on a `schedule` cron trigger works for a daily job. The data fetches will pull from vendor APIs into a database that's persisted somewhere (S3, a managed Postgres, etc.). Trade-off: more pieces, but no host to maintain.

### Alternative: Cloud-managed scheduler

AWS EventBridge, GCP Cloud Scheduler, Azure Logic Apps — all viable. Probably overkill for v1 but mentioned for completeness.

---

## Reporting

| Layer | Choice | Notes |
|---|---|---|
| **Chart rendering** | matplotlib (or Plotly if interactive) | Custom plotting code that renders X/O cells; not stock plotting libraries |
| **Templating** | Jinja2 | The standard Python templating engine |
| **HTML → PDF** | WeasyPrint | Clean output, reliable; alternatives are wkhtmltopdf (older) or headless Chrome (heavy) |
| **Email** | smtplib (stdlib) or a transactional provider (Resend, Postmark, SendGrid) | Transactional provider is more reliable; SMTP is zero-cost |

The advisor receives a PDF attachment in their daily email. The HTML version is also archived for the audit log.

---

## Configuration

Configuration lives in a single TOML file (`config.toml`) covering:

- Data vendor credentials (encrypted at rest)
- Universe definition (which constituents, as of which rebalance date)
- Box-scaling table overrides (in case the advisor wants to deviate from Dorsey's defaults)
- Fundamental filter thresholds
- Composite score weights
- Report recipient address(es) and cadence
- Email server / transactional provider credentials

Configuration changes are version-controlled (the config file is in git), with the exception of credentials, which are pulled from environment variables or a secrets manager.

---

## Testing approach

| Test type | Coverage |
|---|---|
| **Unit tests** | Every public function in the P&F engine, the fundamental gate, the composite scorer |
| **P&F engine fixtures** | Hand-crafted OHLC series with known resulting charts (sourced from Dorsey's book examples) — gold standards for the engine's correctness |
| **Integration tests** | The full pipeline on a tiny universe (5 tickers, 1 year of data) — verifies that data → analysis → report works end to end |
| **Data-quality tests** | Sanity checks on every nightly data refresh (no negative prices, no zero-volume days for liquid names, etc.) |

CI: GitHub Actions running `pytest` + `ruff` + `mypy` on every push.

---

## Deployment

### v1: a single VM

A small Linux VM (Codespaces development, but production deployment on a dedicated VM — e.g., a $5/month DigitalOcean droplet, an EC2 t3.small, or a Hetzner CX21). The bot runs there on a cron schedule, persisting data to a local SQLite file.

Backups: nightly rsync of the SQLite file to S3 or equivalent.

### Why not containerize first?

We can. Docker + a managed scheduler (Cloud Run, Fargate, etc.) is the more modern shape. For v1 the marginal benefit doesn't justify the complexity — a single Python process on a single VM is the right size. Containerize if scale or deployment needs change.

---

## Cost summary (working assumptions)

| Item | Monthly cost |
|---|---|
| Data vendors (see [data-sources.md](data-sources.md)) | ~$54 |
| VM hosting | ~$5–$15 |
| Email / transactional sending | $0 (SMTP via Gmail SMTP relay or similar) |
| Cloud backups (S3) | < $1 |
| Domain (if needed for a dashboard later) | < $2 |
| **Total** | **~$60–$70/month** |

---

## What we are explicitly *not* using (and why)

| Tool | Why we're skipping it |
|---|---|
| **Jupyter notebooks for production** | Fine for exploration; bad for a daily-run cron job. The production pipeline is a real Python package. |
| **A neural-network model for stock prediction** | Premature. The first version of the bot is a transparent rule-based scorer. ML can be layered in Phase 4 or later, after we have backtest data and a clear edge to optimize. |
| **A trading API (Alpaca, IBKR, etc.)** | Explicitly out of scope. The bot does not place trades. |
| **A frontend framework (React, etc.)** | Not needed for v1. A PDF report and email is the interface. An internal dashboard, if it appears, would likely be a small Flask/FastAPI + plain HTML app. |
| **Kafka, Spark, big-data tooling** | The data volumes don't justify it. |

---

## References

- [pandas documentation](https://pandas.pydata.org/docs/)
- [pydantic documentation](https://docs.pydantic.dev/)
- [SQLAlchemy documentation](https://docs.sqlalchemy.org/)
- [Jinja2 documentation](https://jinja.palletsprojects.com/)
- [WeasyPrint documentation](https://weasyprint.org/)
- [pytest documentation](https://docs.pytest.org/)
