from datetime import date

import pytest
from pydantic import ValidationError

from app.models import ExpectedReport, StatusType, UploadedFile
from app.schemas import ExpectedReportCreate
from app.status import report_status


def test_period_must_be_month_start() -> None:
    payload = ExpectedReportCreate(customer_project_id=1, period=date(2026, 6, 1))

    assert payload.period == date(2026, 6, 1)


def test_period_rejects_non_month_start() -> None:
    with pytest.raises(ValidationError):
        ExpectedReportCreate(customer_project_id=1, period=date(2026, 6, 15))


def test_report_status_not_received_without_files() -> None:
    report = ExpectedReport(period=date(2026, 6, 1), customer_project_id=1, files=[])

    assert report_status(report) == StatusType.not_received


def test_report_status_received_until_counts_exist() -> None:
    report = ExpectedReport(period=date(2026, 6, 1), customer_project_id=1)
    report.files = [UploadedFile(original_filename="sales.xlsx", active=True, row_count=10)]

    assert report_status(report) == StatusType.received


def test_report_status_counted_when_rows_and_packs_exist() -> None:
    report = ExpectedReport(period=date(2026, 6, 1), customer_project_id=1)
    report.files = [UploadedFile(original_filename="sales.xlsx", active=True, row_count=10, pack_count=20)]

    assert report_status(report) == StatusType.counted


def test_report_status_feedback_has_priority() -> None:
    report = ExpectedReport(period=date(2026, 6, 1), customer_project_id=1)
    report.files = [UploadedFile(original_filename="sales.xlsx", active=True, status=StatusType.feedback)]

    assert report_status(report) == StatusType.feedback

