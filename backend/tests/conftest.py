"""Test harness: an isolated Postgres database (baysahne_test), migrated with Alembic once per session and
truncated between tests. Push uses the in-memory FakeProvider; e-mail is captured, never sent."""

import io
import os
import re
import tempfile
import uuid
from datetime import timedelta

TEST_MEDIA = tempfile.mkdtemp(prefix="baysahne-test-media-")
os.environ.update(
    APP_ENV="test",
    PUSH_PROVIDER="fake",
    EMAIL_BACKEND="console",
    MEDIA_STORAGE="local",
    MEDIA_LOCAL_ROOT=TEST_MEDIA,
    COOKIE_SECURE="false",
    PUBLIC_API_BASE_URL="http://testserver",
    ADMIN_BASE_URL="http://admin.test",
    CORS_ALLOWED_ORIGINS="http://admin.test",
)

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from alembic import command  # noqa: E402
from app import db as app_db  # noqa: E402
from app.config import BACKEND_DIR, get_settings  # noqa: E402

TEST_URL = get_settings().test_database_url
os.environ["DATABASE_URL"] = TEST_URL
get_settings.cache_clear()
assert get_settings().database_url.endswith("/baysahne_test"), "tests must never run against the dev database"

from app.core.ratelimit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.core.text import utcnow  # noqa: E402
from app.models import AdminRole, AdminUser, Performance, Production, PublicationStatus, Venue, Visibility  # noqa: E402
from app.notifications import providers  # noqa: E402
from app.services import mailer  # noqa: E402

PASSWORD = "Sahne-Test-Parola-2026"


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    engine = create_engine(TEST_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.cmd_opts = type("o", (), {"x": [f"url={TEST_URL}"]})()
    command.upgrade(cfg, "head")
    app_db.configure(TEST_URL)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean(_migrated_database):
    from app.notifications.defaults import ensure_defaults

    engine = app_db.engine()
    with engine.begin() as conn:
        tables = [r[0] for r in conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"))]
        conn.execute(text("TRUNCATE " + ", ".join(tables) + " CASCADE"))
    s = app_db.SessionLocal()
    ensure_defaults(s)
    s.commit()
    s.close()
    limiter.reset()
    yield


@pytest.fixture
def db():
    s = app_db.SessionLocal()
    yield s
    s.close()


@pytest.fixture
def push():
    fake = providers.FakeProvider()
    providers.set_provider(fake)
    yield fake
    providers.set_provider(None)


@pytest.fixture
def mail(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, body: sent.append(
        {"to": to, "subject": subject, "body": body}))
    return sent


def link_token(body: str, kind: str) -> str:
    m = re.search(rf"/{kind}#([A-Za-z0-9_\-]+)", body)
    assert m, body
    return m.group(1)


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def make_user(db, role=AdminRole.editor, email=None, active=True) -> AdminUser:
    u = AdminUser(email=email or f"{role.value}-{uuid.uuid4().hex[:6]}@example.com", full_name=f"Test {role.value}",
                  role=role, password_hash=hash_password(PASSWORD), is_active=active)
    db.add(u)
    db.commit()
    return u


def login(client: TestClient, email: str, password: str = PASSWORD):
    client.headers.update({"X-Requested-With": "baysahne-admin"})
    r = client.post("/api/v1/admin/auth/login", json={"email": email, "password": password})
    return r


@pytest.fixture
def admin_client(client, db):
    u = make_user(db, AdminRole.admin)
    assert login(client, u.email).status_code == 200
    client.user = u
    return client


@pytest.fixture
def editor_client(client, db):
    u = make_user(db, AdminRole.editor)
    assert login(client, u.email).status_code == 200
    client.user = u
    return client


def png_bytes(w=900, h=1200, color=(196, 151, 63), fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, fmt)
    return buf.getvalue()


# ---------------------------------------------------------------- direct data builders


def mk_venue(db, name="Ana Salon") -> Venue:
    v = Venue(name=name, address="Toros Mah.", city="Adana", timezone="Europe/Istanbul")
    db.add(v)
    db.commit()
    return v


def mk_production(db, title="Test Oyunu", status=PublicationStatus.published, **kw) -> Production:
    from app.core.text import slugify

    p = Production(title=title, slug=slugify(title) + "-" + uuid.uuid4().hex[:4], status=status,
                   genres=kw.pop("genres", ["Dram"]), **kw)
    if status == PublicationStatus.published:
        p.first_published_at = p.published_at = utcnow()
    db.add(p)
    db.commit()
    return p


def mk_performance(db, production, venue, hours=48, visibility=Visibility.published, **kw) -> Performance:
    perf = Performance(production_id=production.id, venue_id=venue.id, starts_at=utcnow() + timedelta(hours=hours),
                       visibility=visibility, **kw)
    if visibility == Visibility.published:
        perf.first_published_at = utcnow()
    db.add(perf)
    db.commit()
    db.refresh(perf)
    return perf
