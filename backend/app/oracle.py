from pathlib import Path
from typing import Any

import oracledb
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CustomerProject, CustomerSnapshot, OracleDictionaryQuery, ProjectSnapshot


CUSTOMERS_SQL = "select ID, NAME, CODE from anet.customers t where t.active_df = 1"
PROJECTS_SQL = (
    "select t.TYPE, listagg(t.id,',') within group (order by t.id) optypes "
    "from anet.saletypes t where t.type is not null and t.active_df = 1 group by t.type"
)

_client_init_attempted = False
_client_init_error: str | None = None


def init_oracle_client() -> dict[str, Any]:
    global _client_init_attempted, _client_init_error
    settings = get_settings()
    status = {
        "dsn": settings.oracle_dsn,
        "user": settings.oracle_user,
        "thick_mode_requested": settings.oracle_enable_thick_mode,
        "instant_client_dir": settings.oracle_instant_client_dir,
        "instant_client_dir_exists": Path(settings.oracle_instant_client_dir).exists(),
        "thin_mode": oracledb.is_thin_mode(),
        "client_init_error": _client_init_error,
    }
    if not settings.oracle_enable_thick_mode:
        return status
    if _client_init_attempted:
        status["thin_mode"] = oracledb.is_thin_mode()
        status["client_init_error"] = _client_init_error
        return status
    _client_init_attempted = True
    client_dir = Path(settings.oracle_instant_client_dir)
    if not client_dir.exists():
        _client_init_error = f"Oracle Instant Client directory does not exist: {client_dir}"
        status["client_init_error"] = _client_init_error
        return status
    try:
        oracledb.init_oracle_client(lib_dir=str(client_dir))
        _client_init_error = None
    except Exception as exc:
        _client_init_error = str(exc)
    status["thin_mode"] = oracledb.is_thin_mode()
    status["client_init_error"] = _client_init_error
    return status


def oracle_status() -> dict[str, Any]:
    status = init_oracle_client()
    try:
        settings = get_settings()
        with oracledb.connect(user=settings.oracle_user, password=settings.oracle_password, dsn=settings.oracle_dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("select 1 from dual")
                cursor.fetchone()
        status["connection_ok"] = True
        status["connection_error"] = None
    except Exception as exc:
        status["connection_ok"] = False
        status["connection_error"] = str(exc)
    status["thin_mode"] = oracledb.is_thin_mode()
    return status


def fetch_oracle_rows(sql_text: str) -> list[dict[str, Any]]:
    settings = get_settings()
    status = init_oracle_client()
    if settings.oracle_enable_thick_mode and status.get("client_init_error"):
        raise RuntimeError(f"Oracle Instant Client initialization failed: {status['client_init_error']}")
    with oracledb.connect(user=settings.oracle_user, password=settings.oracle_password, dsn=settings.oracle_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql_text)
            columns = [col[0].lower() for col in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def seed_dictionary_queries(db: Session) -> None:
    defaults = {
        "customers": CUSTOMERS_SQL,
        "projects": PROJECTS_SQL,
        "countries": "",
        "distributors": "",
        "data_types": "",
    }
    for key, sql_text in defaults.items():
        existing = db.query(OracleDictionaryQuery).filter(OracleDictionaryQuery.key == key).one_or_none()
        if not existing:
            db.add(OracleDictionaryQuery(key=key, sql_text=sql_text, active=bool(sql_text)))
    db.commit()


def sync_customers(db: Session, rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in sorted(rows, key=lambda item: int(item["id"])):
        oracle_id = int(row["id"])
        name = str(row.get("name") or "").strip()
        code = str(row.get("code") or "").strip()
        display_name = f"{name} {code}".strip()
        customer = db.query(CustomerSnapshot).filter(CustomerSnapshot.oracle_id == oracle_id).one_or_none()
        if customer:
            customer.name = name
            customer.code = code
            customer.display_name = display_name
            customer.active = True
        else:
            db.add(CustomerSnapshot(oracle_id=oracle_id, name=name, code=code, display_name=display_name))
        count += 1
    db.commit()
    return count


def sync_projects(db: Session, rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        project_type = str(row.get("type") or "").strip()
        if not project_type:
            continue
        optypes = str(row.get("optypes") or "")
        project = db.query(ProjectSnapshot).filter(ProjectSnapshot.type == project_type).one_or_none()
        if project:
            project.optypes = optypes
            project.active = True
        else:
            db.add(ProjectSnapshot(type=project_type, optypes=optypes))
        count += 1
    db.commit()
    return count


def ensure_customer_project_matrix(db: Session) -> int:
    created = 0
    customers = db.query(CustomerSnapshot).filter(CustomerSnapshot.active.is_(True)).all()
    projects = db.query(ProjectSnapshot).filter(ProjectSnapshot.active.is_(True)).all()
    for customer in customers:
        for project in projects:
            exists = (
                db.query(CustomerProject)
                .filter(CustomerProject.customer_id == customer.id, CustomerProject.project_id == project.id)
                .one_or_none()
            )
            if not exists:
                db.add(CustomerProject(customer_id=customer.id, project_id=project.id, active=False))
                created += 1
    db.commit()
    return created
