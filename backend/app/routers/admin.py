from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_roles
from app.models import (
    AccessScope,
    CustomerProject,
    CustomerSnapshot,
    DictionaryItem,
    ExpectedReport,
    OracleDictionaryQuery,
    ProjectSnapshot,
    Role,
    User,
)
from app.oracle import ensure_customer_project_matrix, fetch_oracle_rows, oracle_status, sync_customers, sync_projects
from app.schemas import (
    AccessScopeCreate,
    AccessScopeRead,
    CustomerProjectRead,
    CustomerProjectUpdate,
    CustomerRead,
    DictionaryItemRead,
    ExpectedReportCreate,
    ExpectedReportRead,
    ExpectedReportUpdate,
    OracleDictionaryQueryRead,
    OracleDictionaryQueryUpdate,
    ProjectRead,
    SyncResult,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.security import get_password_hash
from app.serializers import expected_report_to_dict

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles(Role.admin))])


@router.get("/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    exists = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        active=payload.active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    values = payload.model_dump(exclude_unset=True)
    if "password" in values and values["password"]:
        user.hashed_password = get_password_hash(values.pop("password"))
    for key, value in values.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}/scopes", response_model=list[AccessScopeRead])
def list_user_scopes(user_id: int, db: Session = Depends(get_db)) -> list[AccessScope]:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return db.query(AccessScope).filter(AccessScope.user_id == user_id).order_by(AccessScope.id).all()


@router.post("/users/{user_id}/scopes", response_model=AccessScopeRead, status_code=status.HTTP_201_CREATED)
def create_user_scope(user_id: int, payload: AccessScopeCreate, db: Session = Depends(get_db)) -> AccessScope:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    scope = AccessScope(user_id=user_id, **payload.model_dump())
    db.add(scope)
    db.commit()
    db.refresh(scope)
    return scope


@router.delete("/scopes/{scope_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_scope(scope_id: int, db: Session = Depends(get_db)) -> None:
    scope = db.get(AccessScope, scope_id)
    if not scope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scope not found")
    db.delete(scope)
    db.commit()


@router.get("/customers", response_model=list[CustomerRead])
def list_customers(db: Session = Depends(get_db)) -> list[CustomerSnapshot]:
    return db.query(CustomerSnapshot).order_by(CustomerSnapshot.oracle_id).all()


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectSnapshot]:
    return db.query(ProjectSnapshot).order_by(ProjectSnapshot.type).all()


@router.get("/customer-projects", response_model=list[CustomerProjectRead])
def list_customer_projects(db: Session = Depends(get_db)) -> list[CustomerProject]:
    return (
        db.query(CustomerProject)
        .options(joinedload(CustomerProject.customer), joinedload(CustomerProject.project))
        .join(CustomerProject.customer)
        .join(CustomerProject.project)
        .order_by(CustomerSnapshot.oracle_id, ProjectSnapshot.type)
        .all()
    )


@router.patch("/customer-projects/{item_id}", response_model=CustomerProjectRead)
def update_customer_project(item_id: int, payload: CustomerProjectUpdate, db: Session = Depends(get_db)) -> CustomerProject:
    item = db.get(CustomerProject, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer/project pair not found")
    item.active = payload.active
    db.commit()
    db.refresh(item)
    return item


@router.get("/dictionary-queries", response_model=list[OracleDictionaryQueryRead])
def list_dictionary_queries(db: Session = Depends(get_db)) -> list[OracleDictionaryQuery]:
    return db.query(OracleDictionaryQuery).order_by(OracleDictionaryQuery.key).all()


@router.get("/oracle/status")
def get_oracle_status() -> dict:
    return oracle_status()


@router.put("/dictionary-queries/{key}", response_model=OracleDictionaryQueryRead)
def update_dictionary_query(key: str, payload: OracleDictionaryQueryUpdate, db: Session = Depends(get_db)) -> OracleDictionaryQuery:
    item = db.query(OracleDictionaryQuery).filter(OracleDictionaryQuery.key == key).one_or_none()
    if not item:
        item = OracleDictionaryQuery(key=key, sql_text=payload.sql_text, active=payload.active)
        db.add(item)
    else:
        item.sql_text = payload.sql_text
        item.active = payload.active
        item.last_error = None
    db.commit()
    db.refresh(item)
    return item


@router.post("/sync/{key}", response_model=SyncResult)
def sync_dictionary(key: str, db: Session = Depends(get_db)) -> SyncResult:
    query = db.query(OracleDictionaryQuery).filter(OracleDictionaryQuery.key == key).one_or_none()
    if not query or not query.active or not query.sql_text.strip():
        return SyncResult(key=key, warning=f"SQL query for '{key}' is not configured")
    try:
        rows = fetch_oracle_rows(query.sql_text)
        if key == "customers":
            synced = sync_customers(db, rows)
            return SyncResult(key=key, synced=synced, matrix_created=ensure_customer_project_matrix(db))
        if key == "projects":
            synced = sync_projects(db, rows)
            return SyncResult(key=key, synced=synced, matrix_created=ensure_customer_project_matrix(db))
        synced = _sync_dictionary_items(db, key, rows)
        return SyncResult(key=key, synced=synced)
    except Exception as exc:
        query.last_error = str(exc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Oracle sync failed: {exc}") from exc


@router.get("/dictionary-items/{kind}", response_model=list[DictionaryItemRead])
def list_dictionary_items(kind: str, db: Session = Depends(get_db)) -> list[DictionaryItem]:
    return db.query(DictionaryItem).filter(DictionaryItem.kind == kind).order_by(DictionaryItem.name).all()


@router.get("/expected-reports", response_model=list[ExpectedReportRead])
def list_expected_reports(db: Session = Depends(get_db)) -> list[dict]:
    reports = _expected_report_query(db).all()
    return [expected_report_to_dict(report) for report in reports]


@router.post("/expected-reports", response_model=ExpectedReportRead, status_code=status.HTTP_201_CREATED)
def create_expected_report(
    payload: ExpectedReportCreate,
    current_user: User = Depends(require_roles(Role.admin)),
    db: Session = Depends(get_db),
) -> dict:
    customer_project = db.get(CustomerProject, payload.customer_project_id)
    if not customer_project or not customer_project.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer/project pair is inactive or missing")
    report = ExpectedReport(**payload.model_dump(), created_by_id=current_user.id)
    db.add(report)
    db.commit()
    report = _expected_report_query(db).filter(ExpectedReport.id == report.id).one()
    return expected_report_to_dict(report)


@router.patch("/expected-reports/{report_id}", response_model=ExpectedReportRead)
def update_expected_report(report_id: int, payload: ExpectedReportUpdate, db: Session = Depends(get_db)) -> dict:
    report = db.get(ExpectedReport, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expected report not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, key, value)
    db.commit()
    report = _expected_report_query(db).filter(ExpectedReport.id == report_id).one()
    return expected_report_to_dict(report)


def _expected_report_query(db: Session):
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
        .order_by(ExpectedReport.period.desc(), ExpectedReport.id.desc())
    )


def _sync_dictionary_items(db: Session, kind: str, rows: list[dict]) -> int:
    synced = 0
    for row in rows:
        external_id = str(row.get("id") or row.get("external_id") or row.get("code") or row.get("name") or "").strip()
        name = str(row.get("name") or row.get("title") or row.get("value") or external_id).strip()
        code = row.get("code")
        if not name:
            continue
        item = db.query(DictionaryItem).filter(DictionaryItem.kind == kind, DictionaryItem.external_id == external_id).one_or_none()
        if item:
            item.name = name
            item.code = str(code) if code is not None else None
            item.payload = row
            item.active = True
        else:
            db.add(
                DictionaryItem(
                    kind=kind,
                    external_id=external_id,
                    name=name,
                    code=str(code) if code is not None else None,
                    payload=row,
                    active=True,
                )
            )
        synced += 1
    db.commit()
    return synced
