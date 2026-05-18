# DWA Sales Call Checklist

Read this off the phone when the Nasdaq Dorsey Wright sales callback comes in. Listed in priority order — if the call runs short, the Tier 1 items are the must-get.

**Sales:** (212) 312-0333
**Billing:** (804) 525-2270

Identify yourself as a financial advisor evaluating programmatic access for an internal screening tool. Compliance posture: internal-only, advisor-only, no client distribution, no trade execution.

---

## Tier 1 — must get (drives the architecture decision)

1. **NDWEQTA pricing** — single-advisor seat, internal use in an automated screening tool. Get monthly and annual.
2. **SHARADAR/SEP pricing** — same seat, professional tier. (Sharadar Equity Prices is the OHLC database on the same Nasdaq Data Link platform; pairing it with NDWEQTA is the cleanest "all on one platform" architecture.)
3. **NDWEQTA data dictionary or sample CSV** — the exact column list and field definitions. The marketplace page hides this behind login; ask them to email it.
4. **Bullish Percent Index data location** — is BPI series data in NDWEQTA, in any other Nasdaq Data Link database, or platform-only? (Research suggests platform-only; confirm.)

## Tier 2 — very useful

5. **DWA sector classification field** — is it a column in NDWEQTA, or is a separate feed required for DWA's proprietary sector tags?
6. **Update timing SLA** — when after the 4 PM ET market close is new NDWEQTA data available? (Need it ready before the morning report runs.)
7. **License terms PDF** — single-advisor internal-screener use explicitly covered? Per-seat / per-user constraints? Restrictions on derivative works for internal screening?
8. **Trial or evaluation period** — 14 days, 30 days, anything? Lets us verify data quality before committing.
9. **Existing platform subscription bundling or discount** — does the existing DWA Research Platform subscription provide any pricing leverage on the API access?

## Tier 3 — qualifying discounts (potential savings)

10. **Discount programs** — Nasdaq publishes categories: advisors licensed <10 years, CMT-credentialed, academic, volume programs for firms with 10+ advisors. Mention status and ask which apply.

## Bonus question about the manual-export / free path

11. **Platform UI CSV exports** — do the existing platform's CSV exports (watchlists, screener results, RS Matrix) include OHLC columns (Close, Open, High, Low, Volume) alongside the signal fields? And what are the row limits on screener exports? This determines whether the "free" manual-export path requires an outside OHLC vendor or could be self-contained.

---

## What to come away with

Two specific dollar figures (NDWEQTA monthly, SHARADAR/SEP monthly) + license PDF commitment + data dictionary commitment + trial availability. With those, the three-path decision is mechanical:

| If NDWEQTA quote is... | Decision |
|---|---|
| < $100/mo | License it; pair with SHARADAR/SEP or Norgate at the OHLC layer |
| $100–$300/mo | Marginal — depends on advisor's preference for authoritative TA score vs the daily manual step |
| > $300/mo | Skip NDWEQTA. Either go Norgate-only ($53/mo, no DWA in the bot) or use the manual export path ($63/mo, daily 5–10 min advisor effort) |

See [ndw-data-link-alternatives.md](ndw-data-link-alternatives.md) for the full decision framework.
