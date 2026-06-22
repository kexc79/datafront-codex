from sqlalchemy import text

from app.oracle import sync_customers, sync_projects


def test_customer_display_name_is_name_plus_code(db_session):
    sync_customers(db_session, [{"id": 2, "name": "Customer", "code": "CST"}])
    customer = db_session.execute(text("select display_name from customer_snapshots where oracle_id = 2")).scalar_one()

    assert customer == "Customer CST"


def test_project_optypes_are_preserved(db_session):
    sync_projects(db_session, [{"type": "Sales", "optypes": "1,2,3"}])
    optypes = db_session.execute(text("select optypes from project_snapshots where type = 'Sales'")).scalar_one()

    assert optypes == "1,2,3"
