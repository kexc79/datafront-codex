import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_report_access, require_roles
from app.models import CustomerProject, ExpectedReport, FileComment, FileStatusEvent, Role, StatusType, UploadedFile, User
from app.schemas import CommentCreate, ExpectedReportRead, FeedbackCreate, FileMetadataUpdate, UploadedFileRead
from app.serializers import expected_report_to_dict
from app.stats import try_count_rows
from app.status import file_status

router = APIRouter(prefix="/engineer", tags=["engineer"])


@router.get("/reports", response_model=list[ExpectedReportRead])
def list_reports(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    reports = _report_query(db).all()
    visible = [report for report in reports if _can_view(db, current_user, report)]
    return [expected_report_to_dict(report) for report in visible]


@router.get("/tree")
def report_tree(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    reports = [report for report in _report_query(db).all() if _can_view(db, current_user, report)]
    tree: dict[str, dict] = {}
    for report in reports:
        customer_name = report.customer_project.customer.display_name
        project_name = report.customer_project.project.type
        country_name = report.country.name if report.country else "Не указана"
        period = report.period.isoformat()
        distributor_name = report.distributor.name if report.distributor else "Не указан"
        customer = tree.setdefault(customer_name, {"name": customer_name, "projects": {}})
        project = customer["projects"].setdefault(project_name, {"name": project_name, "countries": {}})
        country = project["countries"].setdefault(country_name, {"name": country_name, "periods": {}})
        period_node = country["periods"].setdefault(period, {"period": period, "distributors": {}})
        distributor = period_node["distributors"].setdefault(distributor_name, {"name": distributor_name, "reports": []})
        distributor["reports"].append(expected_report_to_dict(report))
    return _tree_values(tree)


@router.post("/reports/{report_id}/files", response_model=UploadedFileRead, status_code=status.HTTP_201_CREATED)
def upload_file(
    report_id: int,
    upload: UploadFile = File(...),
    current_user: User = Depends(require_roles(Role.admin, Role.engineer)),
    db: Session = Depends(get_db),
) -> UploadedFile:
    report = _report_query(db).filter(ExpectedReport.id == report_id).one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expected report not found")
    require_report_access(db, current_user, report, write=True)
    settings = get_settings()
    original_name = upload.filename or "upload.bin"
    extension = Path(original_name).suffix.lower().lstrip(".")
    if extension not in settings.allowed_extensions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Files with .{extension} extension are not allowed")

    target_dir = settings.upload_path / str(report_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.{extension}"
    target_path = target_dir / stored_name

    max_bytes = settings.max_upload_mb * 1024 * 1024
    digest = hashlib.sha256()
    written = 0
    with target_path.open("wb") as handle:
        while chunk := upload.file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                handle.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large")
            digest.update(chunk)
            handle.write(chunk)

    row_count = try_count_rows(target_path)
    file = UploadedFile(
        expected_report_id=report.id,
        original_filename=original_name,
        stored_filename=stored_name,
        content_type=upload.content_type,
        file_size=written,
        checksum=digest.hexdigest(),
        storage_path=str(target_path),
        uploaded_by_id=current_user.id,
        row_count=row_count,
        status=StatusType.received,
        active=True,
    )
    file.status = file_status(file)
    db.add(file)
    db.flush()
    db.add(FileStatusEvent(file_id=file.id, expected_report_id=report.id, event_type=file.status, created_by_id=current_user.id))
    db.commit()
    db.refresh(file)
    return file


@router.patch("/files/{file_id}", response_model=UploadedFileRead)
def update_file_metadata(
    file_id: int,
    payload: FileMetadataUpdate,
    current_user: User = Depends(require_roles(Role.admin, Role.engineer)),
    db: Session = Depends(get_db),
) -> UploadedFile:
    file = _file_query(db).filter(UploadedFile.id == file_id).one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    require_report_access(db, current_user, file.expected_report, write=True)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(file, key, value)
    new_status = file_status(file)
    if new_status != file.status:
        file.status = new_status
        db.add(FileStatusEvent(file_id=file.id, expected_report_id=file.expected_report_id, event_type=new_status, created_by_id=current_user.id))
    db.commit()
    db.refresh(file)
    return file


@router.post("/files/{file_id}/feedback", response_model=UploadedFileRead)
def mark_feedback(
    file_id: int,
    payload: FeedbackCreate,
    current_user: User = Depends(require_roles(Role.admin, Role.engineer)),
    db: Session = Depends(get_db),
) -> UploadedFile:
    file = _file_query(db).filter(UploadedFile.id == file_id).one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    require_report_access(db, current_user, file.expected_report, write=True)
    file.status = StatusType.feedback
    file.comment = payload.comment
    db.add(FileStatusEvent(file_id=file.id, expected_report_id=file.expected_report_id, event_type=StatusType.feedback, comment=payload.comment, created_by_id=current_user.id))
    db.commit()
    db.refresh(file)
    return file


@router.post("/files/{file_id}/comments")
def add_comment(
    file_id: int,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    file = _file_query(db).filter(UploadedFile.id == file_id).one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    require_report_access(db, current_user, file.expected_report)
    db.add(FileComment(file_id=file.id, comment=payload.comment, created_by_id=current_user.id))
    db.commit()
    return {"ok": True}


@router.get("/files/{file_id}/download")
def download_file(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    file = _file_query(db).filter(UploadedFile.id == file_id).one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    require_report_access(db, current_user, file.expected_report)
    path = Path(file.storage_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file is missing")
    return FileResponse(path, filename=file.original_filename, media_type=file.content_type)


def _report_query(db: Session):
    return (
        db.query(ExpectedReport)
        .options(
            joinedload(ExpectedReport.customer_project).joinedload(CustomerProject.customer),
            joinedload(ExpectedReport.customer_project).joinedload(CustomerProject.project),
            joinedload(ExpectedReport.country),
            joinedload(ExpectedReport.data_type),
            joinedload(ExpectedReport.distributor),
            joinedload(ExpectedReport.files),
        )
        .filter(ExpectedReport.active.is_(True))
        .order_by(ExpectedReport.period.desc(), ExpectedReport.id.desc())
    )


def _file_query(db: Session):
    return db.query(UploadedFile).options(joinedload(UploadedFile.expected_report).joinedload(ExpectedReport.customer_project))


def _can_view(db: Session, user: User, report: ExpectedReport) -> bool:
    try:
        require_report_access(db, user, report)
        return True
    except HTTPException:
        return False


def _tree_values(tree: dict) -> list[dict]:
    customers = []
    for customer in tree.values():
        projects = []
        for project in customer["projects"].values():
            countries = []
            for country in project["countries"].values():
                periods = []
                for period in country["periods"].values():
                    distributors = list(period["distributors"].values())
                    period["distributors"] = distributors
                    periods.append(period)
                country["periods"] = periods
                countries.append(country)
            project["countries"] = countries
            projects.append(project)
        customer["projects"] = projects
        customers.append(customer)
    return customers
