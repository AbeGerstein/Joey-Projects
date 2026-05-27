"""Render the daily report from a DailyReport + per-stock details.

Produces:
- HTML: a self-contained document with charts embedded as base64 data URIs
- PDF: same content rendered via WeasyPrint

The HTML is the source of truth — the PDF is generated from it. This keeps
both representations identical visually.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pnf_bot.report.detail import StockDetailRecord
from pnf_bot.scoring.checklist import ChecklistReport
from pnf_bot.scoring.composite import DailyReport

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_html_report(
    report: DailyReport,
    section_a_details: list[StockDetailRecord],
    section_b_details: list[StockDetailRecord],
) -> str:
    """Render the daily report as a self-contained HTML string.

    The details lists must be ordered the same as report.section_a_top_n
    and report.section_b_top_n respectively. (Caller compiles them via
    compile_stock_detail in that order.)
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template("daily.html.j2")
    return template.render(
        report=report,
        section_a_details=section_a_details,
        section_b_details=section_b_details,
    )


def render_pdf_report(
    report: DailyReport,
    section_a_details: list[StockDetailRecord],
    section_b_details: list[StockDetailRecord],
) -> bytes:
    """Render the daily report as PDF bytes via WeasyPrint.

    WeasyPrint is heavyweight to import (pulls in pango, cairo, etc.)
    so we defer the import until the function is called.
    """
    html = render_html_report(report, section_a_details, section_b_details)
    try:
        from weasyprint import HTML  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError(
            "WeasyPrint is not installed. Add to project deps or skip PDF generation. "
            f"Original error: {e}"
        ) from e
    return HTML(string=html).write_pdf()


def render_checklist_html(report: ChecklistReport) -> str:
    """Render the new checklist-methodology report as HTML.

    The output is the body of the email and the source HTML for PDF generation.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template("checklist_report.html.j2")
    return template.render(report=report)


def render_checklist_pdf(report: ChecklistReport) -> bytes:
    """Render the new checklist report as PDF bytes via WeasyPrint."""
    html = render_checklist_html(report)
    try:
        from weasyprint import HTML  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError(
            "WeasyPrint is not installed. Add to project deps or skip PDF generation. "
            f"Original error: {e}"
        ) from e
    return HTML(string=html).write_pdf()
