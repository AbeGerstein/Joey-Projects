"""Phase 5 — reporting and delivery.

Takes the DailyReport from Phase 4 scoring and produces the actual
PDF email landing in the advisor's inbox each morning.

Public API:
    from pnf_bot.report import (
        render_pnf_chart,
        render_rs_chart,
        StockDetailRecord,
        compile_stock_detail,
        render_html_report,
        render_pdf_report,
        send_report_email,
    )
"""

from pnf_bot.report.charts import render_pnf_chart, render_rs_chart

__all__ = [
    "render_pnf_chart",
    "render_rs_chart",
]
