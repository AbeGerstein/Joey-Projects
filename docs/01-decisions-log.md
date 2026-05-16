# Decisions Log

Append-only log of every material decision made on this project. Each entry captures the date, the decision, the rationale, and the status (whether it's confirmed by the client or still proposed). This document is the audit trail — never delete or rewrite past entries; if a decision is reversed, append a new entry referencing the old one.

Format for each entry:

> **YYYY-MM-DD — Short title**
> - **Decision:** what was decided
> - **Rationale:** why
> - **Status:** Confirmed / Proposed / Superseded by [link]
> - **Context:** any relevant background

---

## 2026-05-15 — Project initiated

- **Decision:** Build a P&F + fundamental analysis stock screening bot for the advisor.
- **Rationale:** Advisor currently performs P&F-based idea generation manually, one chart at a time. A systematic screener can cover a much larger universe and surface candidates the manual process misses, while still leaving final judgement to the advisor.
- **Status:** Confirmed
- **Context:** Project kickoff conversation.

---

## 2026-05-15 — Asset class limited to long US equities

- **Decision:** The bot covers US-listed equities only. Long positions only. No short setups, no futures, no options, no derivatives of any kind.
- **Rationale:** Client requirement. Keeps the scope tractable for v1 and matches how the advisor manages client portfolios.
- **Status:** Confirmed
- **Context:** Explicitly stated by the user during scope conversation.

---

## 2026-05-15 — Output is strictly internal to the advisor

- **Decision:** The report is consumed by the advisor only. Nothing the bot produces is shown to end clients or used as a client-facing document.
- **Rationale:** Internal idea-generation tools have substantially lighter compliance requirements than client-facing material (no FINRA marketing/communications review, no Reg BI considerations on the artifact itself). Limiting scope here reduces compliance overhead significantly.
- **Status:** Confirmed
- **Context:** Explicitly stated by the user. Reinforced in [compliance.md](compliance.md).

---

## 2026-05-15 — P&F is primary; fundamentals are an initial filter

- **Decision:** The methodology stack is: fundamental filter first (remove junk), then P&F evaluation drives the actual scoring and ranking. Fundamentals do not score candidates — they only gate them.
- **Rationale:** Aligns with Dorsey's view in *Point and Figure Charting*: fundamentals tell you *what* to consider; P&F tells you *when* and *whether*. The advisor's edge is P&F; the fundamental filter is just a junk-rejection gate.
- **Status:** Confirmed
- **Context:** User stated "primarily P&F / supply and demand screener but with an initial screen using fundamentals." Design implications captured in [methodology/fundamental-screen.md](methodology/fundamental-screen.md).

---

## 2026-05-15 — 3-box reversal

- **Decision:** Use 3-box reversal for all P&F charts (price charts and RS charts).
- **Rationale:** Dorsey's standard convention throughout *Point and Figure Charting*. The 3-box reversal filters out short-term noise and is what DWA's platform displays by default.
- **Status:** Confirmed
- **Context:** Explicitly stated by the user.

---

## 2026-05-15 — Reference text is Dorsey's *Point and Figure Charting*

- **Decision:** Thomas J. Dorsey's *Point and Figure Charting* is the canonical reference for all P&F-related design decisions. When implementing patterns, signals, trendline rules, RS construction, or BPI, defer to the book's definitions.
- **Rationale:** The book is the methodological foundation of DWA's whole platform; using it as the reference ensures the bot's outputs are consistent with what the advisor expects from DWA-style P&F analysis.
- **Status:** Confirmed
- **Context:** Explicitly stated by the user.

---

## 2026-05-15 — Box scaling: traditional for price charts, percentage for RS charts (PROPOSED)

- **Decision:** Use Dorsey's traditional box-scaling table for stock price charts (price-tiered box sizes — see [methodology/point-and-figure.md](methodology/point-and-figure.md)). Use percentage scaling for RS charts (6.5% boxes for stocks, 3.25% for funds).
- **Rationale:** This is Dorsey's own convention in the book and DWA's platform default. Traditional scaling gives meaningful boxes across the price range; percentage scaling gives proportional sensitivity for RS ratios that can drift far from 100.
- **Status:** Proposed — awaiting confirmation from the advisor.
- **Context:** Recommended by Claude after the user asked what "traditional vs percentage scaling" meant.

---

## 2026-05-15 — DWA access path: replicate from raw OHLC (PROPOSED)

- **Decision:** For v1, replicate P&F charts, RS, and BPI from raw OHLC using publicly documented DWA methodology. Defer licensing the Nasdaq Data Link NDW database until v2 (if at all).
- **Rationale:** Scraping the DWA platform is prohibited by their ToS (see [research/dwa-access.md](research/dwa-access.md)). Licensing the Data Link database requires a separate paid subscription and a sales quote. Replicating from raw OHLC is fully feasible — the math is deterministic and DWA's RS methodology is publicly documented. This path gives us full control, no rate limits, and full inspectability of the screen's logic. The only thing we give up is DWA's proprietary "Technical Attributes" composite score, which the advisor may or may not actually rely on.
- **Status:** Proposed — awaiting confirmation. Alternative options remain on the table: (B) manual CSV export workflow from the existing NDW Research Platform subscription, or (C) license the Nasdaq Data Link NDW database.
- **Context:** Recommendation made after the DWA access research completed.

---

## 2026-05-15 — Document everything thoroughly in the repo

- **Decision:** All decisions, research findings, methodology notes, compliance considerations, and open questions are written into `docs/` inside the repo. The repo is the source of truth. Conversation memory and any external memory store are not.
- **Rationale:** The user explicitly required this. The work is being done for a wealth-management client where audit trails matter; the repo is what survives, gets reviewed by compliance, and can be handed off.
- **Status:** Confirmed
- **Context:** Explicitly stated by the user.

---

## 2026-05-16 — Compliance scope already cleared by the advisor (resolves OQ-006)

- **Decision:** Treat the compliance scope defined in [compliance.md](compliance.md) — internal-only, advisor-only, no client deliverables, no trade execution, recordkeeping in place — as already cleared by the advisor through their firm's compliance framework. No additional CCO sign-off is being requested at the project level; the advisor would not have commissioned this build absent that clearance.
- **Rationale:** Per the user, the advisor confirmed compliance clearance before commissioning the project.
- **Status:** Confirmed
- **Context:** User stated on 2026-05-16: "the advisor would not have commissioned me to do this without knowing that is was ok." Resolves OQ-006. The compliance posture documented in [compliance.md](compliance.md) remains the working framework — if it changes (e.g., the project ever produces client-facing output), the compliance question reopens.

---

## 2026-05-16 — Advisor relies on DWA Technical Attributes score and the full DWA toolset (resolves OQ-008)

- **Decision:** The bot must surface and use DWA's proprietary **Technical Attributes composite score** alongside the underlying P&F signals, Relative Strength data, BPI data, and sector data. The advisor uses every output DWA provides in their daily analysis and wants the bot to do the same.
- **Rationale:** Confirmed by user 2026-05-16. This decision directly drives OQ-002 — the Technical Attributes score is proprietary and cannot be reproduced by replicating from raw OHLC. Only the licensed Nasdaq Data Link NDW database includes it.
- **Status:** Confirmed (resolves OQ-008)
- **Context:** User stated: "yes he uses everything offered by dorsey wright including the technical score in his analysis and i want you to do that as well."

---

## 2026-05-16 — DWA access path: Nasdaq Data Link NDW database (provisional, pending pricing) (partial OQ-002)

- **Decision:** Working choice is **Option A — license the Nasdaq Data Link NDW database(s)** for direct API access to DWA's signals, RS data, Technical Attributes score, BPI data, and sector tags. Final commitment pending the Nasdaq Data Link pricing quote and confirmation (see [research/ndw-data-link-pricing.md](research/ndw-data-link-pricing.md), forthcoming) that the database covers the full set of fields the advisor relies on. Supersedes the earlier provisional recommendation of Option C (replicate from raw OHLC), which was rejected once OQ-008 confirmed the advisor needs the Technical Attributes score.
- **Rationale:** The Technical Attributes score is proprietary to DWA and only available via the licensed Data Link feed (or the DWA platform UI, which is not programmatic). Replication from raw OHLC is no longer viable as the primary path. Option B (manual CSV exports) is rejected because the daily-report cadence (OQ-005) makes a manual export step unworkable.
- **Status:** Provisional — pending pricing and coverage confirmation. Final commitment after research is complete.
- **Context:** User stated 2026-05-16: "most liklely will do the nasdaq data link as that provides everything it just depends on cost." Cost is the only remaining variable.

---

## 2026-05-16 — Universe: full US equities, used for both screening and backtesting (resolves OQ-003 and OQ-007)

- **Decision:** The bot evaluates the **full US equities universe** (NYSE + NASDAQ-listed common stocks). The same universe is used for backtesting, which means historical point-in-time constituent data is required to avoid survivorship bias. A minimum liquidity filter is needed to keep the universe practically tradeable for the advisor — exact thresholds to be defined (see new open question on liquidity floor).
- **Rationale:** Confirmed by user 2026-05-16. Driven by the advisor's preference for the broadest possible idea pool. Note: under Option A (Nasdaq Data Link), the universe is effectively bounded by the coverage of DWA's NDWEQTA database. We will treat NDWEQTA's coverage as the de facto universe definition.
- **Status:** Confirmed (resolves OQ-003 and OQ-007)
- **Context:** User stated for OQ-003: "he wants all stocks in the us equities universe to be included in the evaluation." For OQ-007: "just like where we are screening the entire us equities universie that is the same one we will use for backtesting."

---

## 2026-05-16 — Box scaling: Dorsey's traditional table for price charts (resolves OQ-001)

- **Decision:** Use Dorsey's **traditional price-tiered box-scaling table** for all stock price charts. The table from *Point and Figure Charting* (see [methodology/point-and-figure.md](methodology/point-and-figure.md)) is the authoritative reference. Percentage scaling (6.5% for stocks, 3.25% for funds) remains reserved for Relative Strength charts per Dorsey's own convention.
- **Rationale:** Confirmed by user 2026-05-16. Matches Dorsey's book and the DWA platform default.
- **Status:** Confirmed (resolves OQ-001)
- **Context:** User stated: "the correct box sizing we are using is dorsey wrights traditional one not the percentage one."

---

## 2026-05-16 — Report cadence: daily (resolves OQ-005)

- **Decision:** The bot produces a **daily report**. Delivery format (PDF email vs HTML email vs dashboard) and exact delivery time (pre-market vs after-close) to be settled in Phase 5.
- **Rationale:** Confirmed by user 2026-05-16.
- **Status:** Confirmed (resolves OQ-005)
- **Context:** User stated: "it will be a daily report."

---

## 2026-05-16 — Fundamental filter shape: Option A, quality gate only (PROVISIONAL — defaulted, not explicitly confirmed)

- **Decision:** **Provisionally adopt Option A** for the fundamental initial filter: a narrow quality gate (positive trailing-twelve-month FCF, positive ROE, debt/equity below 3.0, has reported financials within the last 2 quarters). See [methodology/fundamental-screen.md](methodology/fundamental-screen.md).
- **Rationale:** This question (OQ-004) was not explicitly answered by the user on 2026-05-16 when the other open questions were resolved. Per the working preference to make reasonable defaults rather than block, defaulting to Option A — the recommended option, narrow enough not to fight P&F's strength at catching turnarounds. Particularly defensible now that the universe is full US equities, which contains many structurally broken microcap names that need to be filtered out before P&F evaluation.
- **Status:** Provisional — explicitly flagged as defaulted, awaiting advisor override if desired.
- **Context:** OQ-004 left unanswered in user's 2026-05-16 response. Default applied with full transparency in the open-questions log so the advisor can override at any time.
