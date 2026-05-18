"""Send a test report email to verify SMTP delivery works.

Run this from your own machine (or any host with internet access) after
filling in the SMTP credentials at the top. The script:

1. Generates a small synthetic report (no Norgate required)
2. Renders it as HTML and PDF
3. Sends it via SMTP to the configured recipient

Usage:
    python scripts/send_test_email.py

To send via Gmail SMTP (recommended for sending to a Gmail address):
1. Go to https://myaccount.google.com/apppasswords (requires 2FA)
2. Create an "App password" — Google gives you a 16-character password
3. Fill in SMTP_USER (your full Gmail address) and SMTP_APP_PASSWORD below
4. Run this script

The test email has subject "PnF Bot — test email" so it's easy to find/delete.
"""

from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# Add project src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pnf_bot.pnf import construct_chart, construct_rs_chart  # noqa: E402
from pnf_bot.report import (  # noqa: E402
    SmtpConfig,
    compile_stock_detail,
    render_html_report,
    render_pdf_report,
    send_report_email,
)
from pnf_bot.scoring.composite import (  # noqa: E402
    build_daily_report,
    score_stock_in_momentum,
    score_stock_pre_momentum,
)


# ============================================================================
# CONFIGURE THESE BEFORE RUNNING
# ============================================================================

RECIPIENT = "abegerstein@gmail.com"   # where to send the test
SUBJECT = "PnF Bot — test email"

# Gmail SMTP settings (easiest path)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USE_TLS = True

# Fill these in with your Gmail address + an APP PASSWORD
# (NOT your regular Gmail password — generate one at https://myaccount.google.com/apppasswords)
SMTP_USER = "your.gmail.address@gmail.com"   # ← REPLACE
SMTP_APP_PASSWORD = "xxxx xxxx xxxx xxxx"     # ← REPLACE (the 16-char app password)
SMTP_FROM = "your.gmail.address@gmail.com"   # ← REPLACE (usually same as SMTP_USER)

# ============================================================================


def _synthetic_ohlc(start: date, n_days: int, start_price: float, drift: float) -> pd.DataFrame:
    rows = []
    price = start_price
    for i in range(n_days):
        noise = math.sin(i * 0.7) + math.cos(i * 1.3) * 0.5
        price = max(price + drift + noise, 1.0)
        rows.append({
            "open": price, "high": price + 0.5, "low": price - 0.5,
            "close": price, "volume": 1_000_000,
        })
    return pd.DataFrame(rows, index=[start + timedelta(days=i) for i in range(n_days)])


def main() -> int:
    # Validate config before doing any work
    if SMTP_USER == "your.gmail.address@gmail.com" or SMTP_APP_PASSWORD == "xxxx xxxx xxxx xxxx":
        print("ERROR: Edit scripts/send_test_email.py and fill in SMTP_USER and SMTP_APP_PASSWORD")
        print("       at the top of the file before running.")
        print()
        print("To get a Gmail app password:")
        print("  1. Visit https://myaccount.google.com/apppasswords")
        print("  2. Sign in (requires 2FA enabled on your Google account)")
        print("  3. Create a new app password — Google gives you a 16-character string")
        print("  4. Paste it into SMTP_APP_PASSWORD (with or without the spaces — both work)")
        return 1

    # Generate a small synthetic report
    today = date(2026, 5, 18)
    universe = {
        "STRONG1": _synthetic_ohlc(date(2026, 1, 5), 100, start_price=50.0, drift=0.15),
        "STRONG2": _synthetic_ohlc(date(2026, 1, 5), 100, start_price=80.0, drift=0.20),
        "MID1": _synthetic_ohlc(date(2026, 1, 5), 100, start_price=120.0, drift=0.10),
    }
    benchmark = _synthetic_ohlc(date(2026, 1, 5), 100, start_price=50.0, drift=0.02)

    candidates = []
    candidate_charts = {}
    for symbol, ohlc in universe.items():
        price_chart = construct_chart(symbol, ohlc)
        rs_chart = construct_rs_chart(symbol, ohlc, benchmark)
        candidate_charts[symbol] = (price_chart, rs_chart)
        pre = score_stock_pre_momentum(symbol, price_chart, rs_chart, as_of_date=today)
        if pre is not None:
            candidates.append(pre)
        in_mom = score_stock_in_momentum(symbol, price_chart, rs_chart, as_of_date=today)
        if in_mom is not None:
            candidates.append(in_mom)

    report = build_daily_report(candidates, as_of_date=today, section_a_top_n=5, section_b_top_n=5)
    section_a_details = [
        compile_stock_detail(c, *candidate_charts[c.symbol]) for c in report.section_a_top_n
    ]
    section_b_details = [
        compile_stock_detail(c, *candidate_charts[c.symbol]) for c in report.section_b_top_n
    ]

    html = render_html_report(report, section_a_details, section_b_details)
    pdf_bytes = render_pdf_report(report, section_a_details, section_b_details)

    print(f"Report built. HTML: {len(html):,} bytes. PDF: {len(pdf_bytes):,} bytes.")
    print(f"Section A: {len(report.section_a_top_n)}, Section B: {len(report.section_b_top_n)}")
    print(f"Sending to {RECIPIENT} via {SMTP_HOST}:{SMTP_PORT}...")

    smtp = SmtpConfig(
        host=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_APP_PASSWORD.replace(" ", ""),  # Gmail app passwords with or without spaces
        from_address=SMTP_FROM,
        use_tls=SMTP_USE_TLS,
    )

    result = send_report_email(
        smtp_config=smtp,
        recipient_email=RECIPIENT,
        subject_line=SUBJECT,
        html_body=html,
        pdf_bytes=pdf_bytes,
        pdf_filename="pnf_test_report.pdf",
    )

    if result.success:
        print(f"\n✓ Email delivered to {result.recipient} at {result.attempted_at}")
        print("  Check your inbox — search for 'PnF Bot — test email'")
        return 0
    else:
        print(f"\n✗ Email delivery failed: {result.error_message}")
        print("\nCommon causes:")
        print("  - Wrong app password (regenerate at https://myaccount.google.com/apppasswords)")
        print("  - 2FA not enabled on the Google account (required for app passwords)")
        print("  - SMTP_USER doesn't match the account that generated the app password")
        return 2


if __name__ == "__main__":
    sys.exit(main())
