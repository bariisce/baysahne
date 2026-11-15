"""Behaviour under failure: database outages fail fast and cleanly, headers stay correct."""

import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.main import app

# Nothing listens on port 1; the connect timeout bounds the wait even where the OS retries refused connections.
UNREACHABLE = "postgresql+psycopg://baysahne:x@127.0.0.1:1/baysahne"


def test_database_outage_returns_503_quickly(client):
    engine = create_engine(UNREACHABLE, connect_args={"connect_timeout": 2})
    factory = sessionmaker(bind=engine)

    def broken_db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = broken_db
    try:
        started = time.monotonic()
        r = client.get("/api/v1/productions")
        elapsed = time.monotonic() - started
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()

    assert r.status_code == 503
    assert r.json()["error"]["code"] == "service_unavailable"
    assert r.headers["Retry-After"] == "10"
    # An error must not be cached by shared caches like successful public content.
    assert "public" not in r.headers.get("Cache-Control", "")
    assert elapsed < 10


def test_security_and_cache_headers(client):
    ok = client.get("/api/v1/productions")
    assert ok.status_code == 200
    assert ok.headers["X-Content-Type-Options"] == "nosniff"
    assert ok.headers["X-Frame-Options"] == "DENY"
    assert ok.headers["Cache-Control"] == "public, max-age=30"

    missing = client.get("/api/v1/productions/yok-boyle-bir-oyun")
    assert missing.status_code == 404
    assert "public" not in missing.headers.get("Cache-Control", "")

    admin = client.get("/api/v1/admin/auth/me")
    assert admin.headers["Cache-Control"] == "no-store"
    assert admin.headers["X-Content-Type-Options"] == "nosniff"
