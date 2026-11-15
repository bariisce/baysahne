from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, create_engine, func, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def configure(url: str | None = None) -> None:
    global _engine, _SessionLocal
    s = get_settings()
    _engine = create_engine(
        url or s.database_url,
        pool_pre_ping=True,
        pool_timeout=s.db_pool_timeout_seconds,
        connect_args={"connect_timeout": s.db_connect_timeout_seconds},
        future=True,
    )
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)


def engine():
    if _engine is None:
        configure()
    return _engine


def SessionLocal() -> Session:  # noqa: N802 - factory-style name
    if _SessionLocal is None:
        configure()
    return _SessionLocal()


def unavailable_hint() -> str:
    """What to do when the database cannot be reached, phrased for whoever is reading the log."""
    url = engine().url
    where = f"{url.host}:{url.port}" if url.port else str(url.host)
    hint = f"PostgreSQL is not reachable at {where}."
    if get_settings().app_env == "development":
        hint += " Start Docker Desktop, then run `docker compose up -d db` in the repository root."
    return hint


def check_connection() -> bool:
    """One cheap round trip. Used at startup so an unreachable database is reported once, clearly,
    instead of only showing up later as a 503 on every request."""
    try:
        with engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except (OperationalError, PoolTimeoutError):
        return False


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
