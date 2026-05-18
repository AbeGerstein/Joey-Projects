"""End-to-end smoke test with synthetic data.

Exercises the full pipeline (no Norgate required):
1. Generate synthetic OHLC for a handful of fictional symbols
2. Construct P&F charts and RS charts
3. Score candidates pre- and in-momentum
4. Build DailyReport
5. Compile per-stock details
6. Render HTML report (and PDF if WeasyPrint is installed)
7. Save artifacts to ./out/smoke/ for inspection

Run with: python scripts/end_to_end_smoke.py
"""

from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# Add project src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pnf_bot.pnf import construct_chart, construct_rs_chart
from pnf_bot.report import (
    compile_stock_detail,
    render_html_report,
    render_pdf_report,
)
from pnf_bot.scoring.composite import (
    build_daily_report,
    score_stock_in_momentum,
    score_stock_pre_momentum,
)


def synthetic_ohlc(
    start: date, n_days: int, start_price: float, drift: float, vol: float = 1.0
) -> pd.DataFrame:
    """Deterministic synthetic OHLC."""
    rows = []
    price = start_price
    for i in range(n_days):
        noise = math.sin(i * 0.7) * vol + math.cos(i * 1.3) * vol * 0.5
        price += drift + noise
        price = max(price, 1.0)  # don't let synthetic price go below $1
        h = price + 0.5
        l = price - 0.5
        rows.append({"open": price, "high": h, "low": l, "close": price, "volume": 1_000_000})
    return pd.DataFrame(rows, index=[start + timedelta(days=i) for i in range(n_days)])


def main() -> int:
    out_dir = Path(__file__).parent.parent / "out" / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date(2026, 5, 18)

    # Build a fictional universe of 10 stocks with different return profiles
    print("Building synthetic universe...")
    universe = {
        "STRONG1": synthetic_ohlc(date(2026, 1, 5), 100, start_price=50.0, drift=0.15),
        "STRONG2": synthetic_ohlc(date(2026, 1, 5), 100, start_price=80.0, drift=0.20),
        "RECOVER1": synthetic_ohlc(date(2026, 1, 5), 100, start_price=30.0, drift=0.10),
        "STEADY1": synthetic_ohlc(date(2026, 1, 5), 100, start_price=100.0, drift=0.05),
        "STEADY2": synthetic_ohlc(date(2026, 1, 5), 100, start_price=60.0, drift=0.03),
        "FLAT1": synthetic_ohlc(date(2026, 1, 5), 100, start_price=40.0, drift=0.0),
        "DECLINE1": synthetic_ohlc(date(2026, 1, 5), 100, start_price=50.0, drift=-0.05),
        "PARABOLIC1": synthetic_ohlc(date(2026, 1, 5), 100, start_price=20.0, drift=0.40, vol=0.2),
        "TINY1": synthetic_ohlc(date(2026, 1, 5), 100, start_price=15.0, drift=0.08),
        "MID1": synthetic_ohlc(date(2026, 1, 5), 100, start_price=120.0, drift=0.10),
    }
    benchmark = synthetic_ohlc(date(2026, 1, 5), 100, start_price=50.0, drift=0.02)

    # Score each stock
    print("Scoring stocks...")
    candidates = []
    candidate_charts = {}  # symbol -> (chart, rs_chart) for later detail compilation

    for symbol, ohlc in universe.items():
        try:
            price_chart = construct_chart(symbol, ohlc)
            rs_chart = construct_rs_chart(symbol, ohlc, benchmark)
        except Exception as e:  # noqa: BLE001
            print(f"  Skipping {symbol}: {e}")
            continue
        candidate_charts[symbol] = (price_chart, rs_chart)

        pre = score_stock_pre_momentum(symbol, price_chart, rs_chart, as_of_date=today)
        if pre is not None:
            candidates.append(pre)
            print(f"  {symbol}: pre-momentum score {pre.final_score:.3f}")
        in_mom = score_stock_in_momentum(symbol, price_chart, rs_chart, as_of_date=today)
        if in_mom is not None:
            candidates.append(in_mom)
            print(f"  {symbol}: in-momentum score {in_mom.final_score:.3f}")

    # Build daily report
    print(f"\nTotal candidates: {len(candidates)}")
    report = build_daily_report(candidates, as_of_date=today, section_a_top_n=5, section_b_top_n=5)
    print(f"Section A: {len(report.section_a_top_n)}, Section B: {len(report.section_b_top_n)}, "
          f"New last night: {len(report.new_patterns_last_night)}")

    # Compile per-stock details
    print("Compiling per-stock details and rendering charts...")
    section_a_details = []
    for cand in report.section_a_top_n:
        price_chart, rs_chart = candidate_charts[cand.symbol]
        section_a_details.append(compile_stock_detail(cand, price_chart, rs_chart))
    section_b_details = []
    for cand in report.section_b_top_n:
        price_chart, rs_chart = candidate_charts[cand.symbol]
        section_b_details.append(compile_stock_detail(cand, price_chart, rs_chart))

    # Render HTML
    print("Rendering HTML report...")
    html = render_html_report(report, section_a_details, section_b_details)
    html_path = out_dir / "smoke_report.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  Wrote {html_path} ({len(html):,} bytes)")

    # Render PDF
    print("Rendering PDF report (skipped if WeasyPrint not installed)...")
    try:
        pdf_bytes = render_pdf_report(report, section_a_details, section_b_details)
        pdf_path = out_dir / "smoke_report.pdf"
        pdf_path.write_bytes(pdf_bytes)
        print(f"  Wrote {pdf_path} ({len(pdf_bytes):,} bytes)")
    except RuntimeError as e:
        print(f"  Skipped PDF: {e}")

    print("\nSmoke test complete. Inspect output at:", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
