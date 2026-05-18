"""Email delivery for the daily report.

Uses SMTP via Python's stdlib (no external dependencies). The SMTP
credentials and recipient come from config.toml per docs/research/
norgate-data.md and the [email] / [report] config sections.

The report is sent as an HTML body for inline rendering in Yahoo Mail
(the advisor's mail provider per the locked decisions) with the PDF
attached for offline / archival reference.

A delivery attempt returns a DeliveryResult capturing success/failure
and timestamp for the audit log.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from datetime import datetime, UTC
from email.message import EmailMessage


@dataclass(frozen=True)
class SmtpConfig:
    """SMTP delivery parameters (copied from config.toml [email] section)."""

    host: str
    port: int
    username: str
    password: str
    from_address: str
    use_tls: bool = True


@dataclass(frozen=True)
class DeliveryResult:
    """Outcome of one delivery attempt."""

    success: bool
    attempted_at: datetime
    recipient: str
    subject: str
    error_message: str | None = None


def send_report_email(
    smtp_config: SmtpConfig,
    recipient_email: str,
    subject_line: str,
    html_body: str,
    pdf_bytes: bytes | None = None,
    *,
    pdf_filename: str = "daily_pnf_report.pdf",
) -> DeliveryResult:
    """Send the daily report via SMTP.

    The HTML is the email body (inline-rendered by mail clients). The PDF
    is attached if provided. Returns a DeliveryResult.

    Failures are caught and reported via the result rather than raising,
    so the caller can persist the failure to the audit log and continue.
    """
    attempted_at = datetime.now(UTC)
    msg = EmailMessage()
    msg["Subject"] = subject_line
    msg["From"] = smtp_config.from_address
    msg["To"] = recipient_email
    msg.set_content(
        "This report is best viewed in HTML. The PDF attachment contains the same content."
    )
    msg.add_alternative(html_body, subtype="html")
    if pdf_bytes is not None:
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=pdf_filename,
        )

    try:
        if smtp_config.use_tls:
            with smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30) as srv:
                srv.starttls()
                srv.login(smtp_config.username, smtp_config.password)
                srv.send_message(msg)
        else:
            with smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30) as srv:
                srv.login(smtp_config.username, smtp_config.password)
                srv.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        return DeliveryResult(
            success=False,
            attempted_at=attempted_at,
            recipient=recipient_email,
            subject=subject_line,
            error_message=str(e),
        )

    return DeliveryResult(
        success=True,
        attempted_at=attempted_at,
        recipient=recipient_email,
        subject=subject_line,
    )
