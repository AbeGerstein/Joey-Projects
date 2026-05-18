"""Tests for email delivery and audit logging."""

from __future__ import annotations

import smtplib
from datetime import date, datetime, UTC
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pnf_bot.data import storage
from pnf_bot.report.audit import persist_report_to_audit_log
from pnf_bot.report.delivery import DeliveryResult, SmtpConfig, send_report_email


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def _smtp_config() -> SmtpConfig:
    return SmtpConfig(
        host="smtp.example.com",
        port=587,
        username="user",
        password="secret",
        from_address="bot@example.com",
        use_tls=True,
    )


class TestSendReportEmail:
    @patch("smtplib.SMTP")
    def test_successful_delivery(self, mock_smtp_class) -> None:  # noqa: ANN001
        """SMTP delivery success returns a DeliveryResult with success=True."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = send_report_email(
            smtp_config=_smtp_config(),
            recipient_email="advisor@example.com",
            subject_line="Daily PnF stock report",
            html_body="<html><body>Hello</body></html>",
            pdf_bytes=b"%PDF-1.4 fake pdf content",
        )
        assert result.success is True
        assert result.error_message is None
        assert result.recipient == "advisor@example.com"
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "secret")
        mock_server.send_message.assert_called_once()

    @patch("smtplib.SMTP")
    def test_smtp_exception_captured_in_result(self, mock_smtp_class) -> None:  # noqa: ANN001
        """SMTP errors do not raise — they're captured in DeliveryResult."""
        mock_smtp_class.side_effect = smtplib.SMTPException("connection refused")

        result = send_report_email(
            smtp_config=_smtp_config(),
            recipient_email="advisor@example.com",
            subject_line="Daily PnF stock report",
            html_body="<html></html>",
        )
        assert result.success is False
        assert "connection refused" in result.error_message

    @patch("smtplib.SMTP")
    def test_no_pdf_attachment_still_sends(self, mock_smtp_class) -> None:  # noqa: ANN001
        """A delivery with pdf_bytes=None works (HTML-only email)."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        result = send_report_email(
            smtp_config=_smtp_config(),
            recipient_email="advisor@example.com",
            subject_line="Test",
            html_body="<html></html>",
            pdf_bytes=None,
        )
        assert result.success is True


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLog:
    @pytest.fixture
    def tmp_db_and_archive(self, tmp_path: Path) -> tuple[Path, Path]:
        db_path = tmp_path / "test_pnf.db"
        archive_dir = tmp_path / "archive"
        storage.init_database(db_path)
        return db_path, archive_dir

    def test_persists_html_and_pdf(self, tmp_db_and_archive: tuple[Path, Path]) -> None:
        db_path, archive_dir = tmp_db_and_archive
        entry = persist_report_to_audit_log(
            db_path=db_path,
            report_date=date(2026, 5, 18),
            recipient_email="advisor@example.com",
            subject_line="Daily PnF stock report",
            html_content="<html><body>Report</body></html>",
            pdf_bytes=b"%PDF-1.4 fake pdf",
            archive_dir=archive_dir,
            parameter_snapshot={"weight_a": 0.30},
            candidate_count_section_a=8,
            candidate_count_section_b=10,
            candidate_count_new_last_night=2,
        )
        assert entry.archive_id > 0
        assert entry.recipient_email == "advisor@example.com"
        assert entry.candidate_count_section_a == 8
        assert Path(entry.html_path).exists()
        assert Path(entry.pdf_path).exists()
        assert entry.parameter_snapshot_sha256

    def test_persists_html_only_when_no_pdf(self, tmp_db_and_archive: tuple[Path, Path]) -> None:
        db_path, archive_dir = tmp_db_and_archive
        entry = persist_report_to_audit_log(
            db_path=db_path,
            report_date=date(2026, 5, 18),
            recipient_email="advisor@example.com",
            subject_line="Daily PnF stock report",
            html_content="<html></html>",
            pdf_bytes=None,
            archive_dir=archive_dir,
            parameter_snapshot={},
            candidate_count_section_a=0,
            candidate_count_section_b=0,
            candidate_count_new_last_night=0,
        )
        assert entry.pdf_path is None
        assert Path(entry.html_path).exists()

    def test_delivery_result_attached_to_audit_entry(
        self, tmp_db_and_archive: tuple[Path, Path]
    ) -> None:
        db_path, archive_dir = tmp_db_and_archive
        delivery_result = DeliveryResult(
            success=True,
            attempted_at=datetime.now(UTC),
            recipient="advisor@example.com",
            subject="Daily PnF stock report",
        )
        entry = persist_report_to_audit_log(
            db_path=db_path,
            report_date=date(2026, 5, 18),
            recipient_email="advisor@example.com",
            subject_line="Daily PnF stock report",
            html_content="<html></html>",
            pdf_bytes=None,
            archive_dir=archive_dir,
            parameter_snapshot={},
            candidate_count_section_a=0,
            candidate_count_section_b=0,
            candidate_count_new_last_night=0,
            delivery_result=delivery_result,
        )
        assert entry.delivery_status == "sent"
        assert entry.delivery_attempted_at is not None

    def test_failed_delivery_marks_status_failed(
        self, tmp_db_and_archive: tuple[Path, Path]
    ) -> None:
        db_path, archive_dir = tmp_db_and_archive
        delivery_result = DeliveryResult(
            success=False,
            attempted_at=datetime.now(UTC),
            recipient="advisor@example.com",
            subject="Daily PnF stock report",
            error_message="SMTP connection refused",
        )
        entry = persist_report_to_audit_log(
            db_path=db_path,
            report_date=date(2026, 5, 18),
            recipient_email="advisor@example.com",
            subject_line="Daily PnF stock report",
            html_content="<html></html>",
            pdf_bytes=None,
            archive_dir=archive_dir,
            parameter_snapshot={},
            candidate_count_section_a=0,
            candidate_count_section_b=0,
            candidate_count_new_last_night=0,
            delivery_result=delivery_result,
        )
        assert entry.delivery_status == "failed"
        assert "connection refused" in entry.delivery_error
