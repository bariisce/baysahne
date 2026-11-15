from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app import db as app_db
from app.db import Base


def test_models_match_migrations():
    """The Alembic-migrated schema must equal the SQLAlchemy models (no un-migrated model changes)."""
    with app_db.engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []


def test_core_constraints_exist():
    insp = inspect(app_db.engine())
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("notification_jobs")}
    assert ("dedupe_key",) in uniques
    deliveries = {tuple(u["column_names"]) for u in insp.get_unique_constraints("notification_deliveries")}
    assert ("job_id", "device_id") in deliveries
    assert ("installation_id",) in {tuple(u["column_names"]) for u in insp.get_unique_constraints("push_devices")}
    checks = {c["name"] for c in insp.get_check_constraints("productions")}
    assert "ck_productions_production_status" in checks
