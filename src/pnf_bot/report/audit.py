"""Audit log — persists every report generation to the SQLite
reports_archive table for compliance recordkeeping.

Per docs/compliance.md (and SEC Rule 17a-4): every report the bot
produces must be retained with timestamp, contents, recipient, and
the parameter snapshot that produced it. This module handles that.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from pnf_bot.data import storage
from pnf_bot.report.delivery import DeliveryResult


@dataclass(frozen=True)
class ReportArchiveEntry:
    """One row in the reports_archive audit log."""

    archive_id: int
    generated_at: datetime
    report_date: date
    recipient_email: str
    subject_line: str
    pdf_path: str | None
    html_path: str | None
    candidate_count_section_a: int
    candidate_count_section_b: int
    candidate_count_new_last_night: int
    delivery_status: str
    delivery_attempted_at: datetime | None
    delivery_error: str | None
    parameter_snapshot_sha256: str


def persist_report_to_audit_log(
    db_path: Path | str,
    report_date: date,
    recipient_email: str,
    subject_line: str,
    html_content: str,
    pdf_bytes: bytes | None,
    archive_dir: Path | str,
    parameter_snapshot: dict,
    candidate_count_section_a: int,
    candidate_count_section_b: int,
    candidate_count_new_last_night: int,
    delivery_result: DeliveryResult | None = None,
) -> ReportArchiveEntry:
    """Write the report's contents to disk AND insert an audit row.

    Steps:
    1. Save the HTML and PDF (if present) to archive_dir with date-stamped filenames
    2. Compute a SHA-256 of the parameter snapshot (full JSON dict)
    3. Insert into reports_archive with all metadata
    4. Return the archive entry record

    Idempotent within a single date — re-running for the same date will
    create new file versions (timestamped) and a new archive row.
    """
    archive_dir_path = Path(archive_dir)
    archive_dir_path.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC)
    timestamp_str = generated_at.strftime("%Y%m%d_%H%M%S")

    html_path = archive_dir_path / f"report_{report_date.isoformat()}_{timestamp_str}.html"
    html_path.write_text(html_content, encoding="utf-8")
    pdf_path = None
    if pdf_bytes is not None:
        pdf_path = archive_dir_path / f"report_{report_date.isoformat()}_{timestamp_str}.pdf"
        pdf_path.write_bytes(pdf_bytes)

    snapshot_json = json.dumps(parameter_snapshot, sort_keys=True, default=str)
    snapshot_sha = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()

    with storage.get_session(db_path) as session:
        row = storage.ReportArchive(
            generated_at=generated_at,
            report_date=report_date,
            recipient_email=recipient_email,
            subject_line=subject_line,
            pdf_path=str(pdf_path) if pdf_path else None,
            html_path=str(html_path),
            parameter_snapshot_json=snapshot_json,
            candidate_count_section_a=candidate_count_section_a,
            candidate_count_section_b=candidate_count_section_b,
            candidate_count_new_last_night=candidate_count_new_last_night,
            delivery_status="sent" if (delivery_result and delivery_result.success) else (
                "failed" if delivery_result else "pending"
            ),
            delivery_attempted_at=delivery_result.attempted_at if delivery_result else None,
            delivery_error=delivery_result.error_message if delivery_result else None,
        )
        session.add(row)
        session.commit()
        row_id = row.id

    return ReportArchiveEntry(
        archive_id=row_id,
        generated_at=generated_at,
        report_date=report_date,
        recipient_email=recipient_email,
        subject_line=subject_line,
        pdf_path=str(pdf_path) if pdf_path else None,
        html_path=str(html_path),
        candidate_count_section_a=candidate_count_section_a,
        candidate_count_section_b=candidate_count_section_b,
        candidate_count_new_last_night=candidate_count_new_last_night,
        delivery_status="sent" if (delivery_result and delivery_result.success) else (
            "failed" if delivery_result else "pending"
        ),
        delivery_attempted_at=delivery_result.attempted_at if delivery_result else None,
        delivery_error=delivery_result.error_message if delivery_result else None,
        parameter_snapshot_sha256=snapshot_sha,
    )
