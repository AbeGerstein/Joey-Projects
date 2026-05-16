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
