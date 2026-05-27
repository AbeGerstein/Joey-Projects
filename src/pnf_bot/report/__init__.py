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

from pnf_bot.report.audit import (
    ReportArchiveEntry,
    persist_report_to_audit_log,
)
from pnf_bot.report.charts import render_pnf_chart, render_rs_chart
from pnf_bot.report.delivery import (
    DeliveryResult,
    SmtpConfig,
    send_report_email,
)
from pnf_bot.report.detail import (
    SignalHistoryEntry,
    StockDetailRecord,
    compile_stock_detail,
)
from pnf_bot.report.render import (
    render_checklist_html,
    render_checklist_pdf,
    render_html_report,
    render_pdf_report,
)

__all__ = [
    "DeliveryResult",
    "ReportArchiveEntry",
    "SignalHistoryEntry",
    "SmtpConfig",
    "StockDetailRecord",
    "compile_stock_detail",
    "persist_report_to_audit_log",
    "render_checklist_html",
    "render_checklist_pdf",
    "render_html_report",
    "render_pdf_report",
    "render_pnf_chart",
    "render_rs_chart",
    "send_report_email",
]
