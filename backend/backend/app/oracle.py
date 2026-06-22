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


def init_oracle_client() -> None:
    settings = get_settings()
    if not settings.oracle_enable_thick_mode:
        return
    client_dir = Path(settings.oracle_instant_client_dir)
    if client_dir.exists():
        try:
            oracledb.init_oracle_client(lib_dir=str(client_dir))
        except Exception:
            pass


def fetch_oracle_rows(sql_text: str) -> list[dict[str, Any]]:
    settings = get_settings()
    init_oracle_client()
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

