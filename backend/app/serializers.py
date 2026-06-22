from app.models import ExpectedReport
from app.status import report_status


def expected_report_to_dict(report: ExpectedReport) -> dict:
    return {
        "id": report.id,
        "customer_project": {
            "id": report.customer_project.id,
            "active": report.customer_project.active,
            "customer": {
                "id": report.customer_project.customer.id,
                "oracle_id": report.customer_project.customer.oracle_id,
                "name": report.customer_project.customer.name,
                "code": report.customer_project.customer.code,
                "display_name": report.customer_project.customer.display_name,
                "active": report.customer_project.customer.active,
            },
            "project": {
                "id": report.customer_project.project.id,
                "type": report.customer_project.project.type,
                "optypes": report.customer_project.project.optypes,
                "active": report.customer_project.project.active,
            },
        },
        "country": _dictionary_item(report.country),
        "data_type": _dictionary_item(report.data_type),
        "distributor": _dictionary_item(report.distributor),
        "period": report.period,
        "deadline": report.deadline,
        "active": report.active,
        "status": report_status(report),
        "files": [
            {
                "id": file.id,
                "original_filename": file.original_filename,
                "content_type": file.content_type,
                "file_size": file.file_size,
                "checksum": file.checksum,
                "uploaded_at": file.uploaded_at,
                "row_count": file.row_count,
                "pack_count": file.pack_count,
                "comment": file.comment,
                "active": file.active,
                "status": file.status,
            }
            for file in sorted(report.files, key=lambda item: item.uploaded_at, reverse=True)
        ],
    }


def _dictionary_item(item) -> dict | None:
    if not item:
        return None
    return {
        "id": item.id,
        "kind": item.kind,
        "external_id": item.external_id,
        "name": item.name,
        "code": item.code,
        "active": item.active,
    }

