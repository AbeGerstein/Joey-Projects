# P&F + Fundamental Stock Screening Bot

An advisor-facing screening tool that uses **Point and Figure (P&F) technical analysis** to surface stocks that are *about to enter* a period of upward momentum — catching the inflection before the move plays out, not confirming it after the fact. Pure supply-and-demand analysis applied systematically across the US equity universe.

This project is being built for a financial advisor at a wealth management firm. The bot is **strictly an internal idea-generation aid** — it produces a daily report for the advisor; it does not produce client-facing material and it does not place trades.

---

## Status

Project initiated **2026-05-15**. Currently in **Phase 0 (Discovery & Compliance)**. No production code yet; documentation and methodology are being assembled first.

See [docs/00-project-outline.md](docs/00-project-outline.md) for the full phased plan and where we are within it.

---

## Methodology at a glance

- **Pure P&F / supply-and-demand screener** following the conventions in **Thomas J. Dorsey's *Point and Figure Charting*** — chart construction, signal patterns, relative strength, bullish percent indicators, sector rotation. No fundamental filter — per the advisor's view (and Dorsey's), the chart already reflects fundamentals via supply and demand.
- **Pre-momentum focus:** the bot specifically targets stocks at the *start* of a potential momentum move — coiling patterns, near-breakout setups, regime-change signals — not stocks already in motion. Names already extended past their breakout points are deprioritized.
- **Output:** a ranked daily report of pre-momentum candidates with P&F chart images, signal rationale, and suggested entry/stop levels.

For the full methodology see [docs/methodology/](docs/methodology/), particularly [docs/methodology/pre-momentum-detection.md](docs/methodology/pre-momentum-detection.md) which captures the pattern catalog and scoring framework for the predictive intent.

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
| [docs/methodology/pre-momentum-detection.md](docs/methodology/pre-momentum-detection.md) | Pattern catalog and scoring logic for catching the start of a move |
| ~~docs/methodology/fundamental-screen.md~~ | *(Superseded — fundamental filter removed from the project on 2026-05-16)* |
| [docs/research/dwa-access.md](docs/research/dwa-access.md) | How to legitimately access DWA data — APIs, exports, ToS, alternatives |
| [docs/research/ndw-data-link-pricing.md](docs/research/ndw-data-link-pricing.md) | NDWEQTA coverage and pricing investigation |
| [docs/research/ndw-data-link-alternatives.md](docs/research/ndw-data-link-alternatives.md) | Alternatives to NDWEQTA if pricing is prohibitive |
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
