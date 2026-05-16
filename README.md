# P&F + Fundamental Stock Screening Bot

An advisor-facing screening tool that combines **Point and Figure (P&F) technical analysis** with a **fundamental quality filter** to surface stocks showing high-conviction *pre-breakout* setups — the kind of evidence a skilled P&F practitioner would weigh when forming a buy thesis, applied systematically across a universe of names.

This project is being built for a financial advisor at a wealth management firm. The bot is **strictly an internal idea-generation aid** — it produces a periodic report for the advisor; it does not produce client-facing material and it does not place trades.

---

## Status

Project initiated **2026-05-15**. Currently in **Phase 0 (Discovery & Compliance)**. No production code yet; documentation and methodology are being assembled first.

See [docs/00-project-outline.md](docs/00-project-outline.md) for the full phased plan and where we are within it.

---

## Methodology at a glance

- **Primary engine:** Point and Figure analysis following the conventions in **Thomas J. Dorsey's *Point and Figure Charting*** — chart construction, signal patterns, relative strength, bullish percent indicators, sector rotation. P&F is the supply-and-demand lens used to identify setups.
- **Initial filter:** a narrow fundamental gate (quality of balance sheet, basic growth and earnings health) that removes outright junk before P&F evaluation. Per Dorsey's view, fundamentals decide *what* to consider; P&F decides *when* and *whether* to act.
- **Output:** a ranked report of pre-breakout candidates with chart images, signal rationale, suggested entry/stop levels, and supporting fundamentals.

For the full methodology see [docs/methodology/](docs/methodology/).

---

## Hard constraints

| Constraint | Detail |
|---|---|
| **Asset class** | US equities only |
| **Direction** | Long positions only — no shorts, no futures, no derivatives |
| **Audience** | The advisor only — internal idea generation, never shown to end clients |
| **Reference text** | Dorsey, *Point and Figure Charting* — defer to the book's conventions for P&F definitions and rules |
| **P&F conventions** | 3-box reversal; box scaling per Dorsey's traditional table for price charts, percentage scaling for RS charts |
| **Data ethics** | No scraping of Dorsey Wright / Nasdaq DWA platforms — explicit ToS violation. See [docs/research/dwa-access.md](docs/research/dwa-access.md) |

---

## Documentation map

This repository contains the canonical project documentation. Read these in roughly this order:

| Doc | Purpose |
|---|---|
| [docs/00-project-outline.md](docs/00-project-outline.md) | The phased build plan, Phase 0 → Phase 6 |
| [docs/01-decisions-log.md](docs/01-decisions-log.md) | Append-only log of every material project decision |
| [docs/02-open-questions.md](docs/02-open-questions.md) | Unresolved items requiring client input or further research |
| [docs/compliance.md](docs/compliance.md) | Compliance scope, ToS adherence, record-keeping, disclaimers |
| [docs/methodology/point-and-figure.md](docs/methodology/point-and-figure.md) | P&F chart construction, box scaling, signals, trendlines |
| [docs/methodology/relative-strength.md](docs/methodology/relative-strength.md) | DWA RS construction and signals |
| [docs/methodology/bullish-percent-index.md](docs/methodology/bullish-percent-index.md) | BPI calculation, market posture, sector BPIs |
| [docs/methodology/fundamental-screen.md](docs/methodology/fundamental-screen.md) | The fundamental initial-filter design |
| [docs/research/dwa-access.md](docs/research/dwa-access.md) | How to legitimately access DWA data — APIs, exports, ToS, alternatives |
| [docs/data-sources.md](docs/data-sources.md) | Evaluation of OHLC, fundamentals, and DWA data vendors |
| [docs/tech-stack.md](docs/tech-stack.md) | Language, libraries, storage, scheduler, reporting |

---

## Tech stack (planned)

- **Language:** Python (pandas, numpy)
- **P&F engine:** custom implementation following Dorsey's rules (no production-grade library exists)
- **Storage:** SQLite to start; Postgres + TimescaleDB if scale demands it
- **Scheduler:** cron or GitHub Actions, daily after market close
- **Reporting:** Jinja2 → HTML → WeasyPrint for PDF; email delivery to the advisor

See [docs/tech-stack.md](docs/tech-stack.md) for rationale.

---

## How documentation is maintained

Everything material that happens on this project gets written into `docs/`. Decisions are appended to the decisions log. New research findings get their own file under `docs/research/`. Methodology details get expanded as we implement them. **The `docs/` tree is the source of truth** — the conversation history and any external memory store are not.

A teammate, the advisor, or a compliance reviewer should be able to open this repository six months from now with zero context and reconstruct the project's reasoning. That is the bar.
