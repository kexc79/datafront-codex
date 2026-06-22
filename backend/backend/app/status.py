from app.models import ExpectedReport, StatusType, UploadedFile


def file_status(file: UploadedFile) -> StatusType:
    if file.status == StatusType.feedback:
        return StatusType.feedback
    if file.row_count is not None and file.pack_count is not None:
        return StatusType.counted
    return StatusType.received


def report_status(report: ExpectedReport) -> StatusType:
    active_files = [item for item in report.files if item.active]
    if not active_files:
        return StatusType.not_received
    if any(item.status == StatusType.feedback for item in active_files):
        return StatusType.feedback
    if all(item.row_count is not None and item.pack_count is not None for item in active_files):
        return StatusType.counted
    return StatusType.received

