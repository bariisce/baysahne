from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.text import utcnow
from app.models import AdminInvitation, AdminRole, AdminUser, AuditLog
from tests.conftest import PASSWORD, link_token, login, make_user


def test_unauthenticated_admin_requests_are_rejected(client):
    r = client.get("/api/v1/admin/dashboard")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_login_sets_httponly_strict_cookie_and_me_works(client, db):
    u = make_user(db, AdminRole.editor)
    r = login(client, u.email)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/v1/admin/auth/me").json()["user"]["email"] == u.email


def test_wrong_password_and_unknown_email_give_same_error(client, db):
    u = make_user(db)
    a = login(client, u.email, "yanlis-parola-123")
    b = login(client, "kimse@example.com", "yanlis-parola-123")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_account_locks_after_repeated_failures(client, db):
    u = make_user(db)
    for _ in range(5):
        assert login(client, u.email, "yanlis-parola-123").status_code == 401
    r = login(client, u.email)  # correct password, but locked
    assert r.status_code == 423
    db.expire_all()
    assert db.get(AdminUser, u.id).locked_until is not None
    assert db.query(AuditLog).filter_by(action="auth.locked").count() == 1


def test_login_rate_limit(client, db):
    u = make_user(db)
    codes = [login(client, u.email, f"bad-password-{i}").status_code for i in range(12)]
    assert 429 in codes


def test_csrf_header_required_for_unsafe_methods(client, db):
    u = make_user(db)
    r = client.post("/api/v1/admin/auth/login", json={"email": u.email, "password": PASSWORD})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"
    r = client.post("/api/v1/admin/auth/login", json={"email": u.email, "password": PASSWORD},
                    headers={"X-Requested-With": "baysahne-admin", "Origin": "https://evil.example"})
    assert r.status_code == 403


def test_editor_cannot_use_admin_only_endpoints(editor_client):
    assert editor_client.get("/api/v1/admin/users").status_code == 403
    assert editor_client.post("/api/v1/admin/invitations", json={
        "email": "x@example.com", "full_name": "X", "role": "admin"}).status_code == 403
    assert editor_client.put("/api/v1/admin/notifications/policy", json={
        "reminder_lead_minutes": [60], "max_per_device_per_day": 1, "broadcast_cooldown_minutes": 0}).status_code == 403
    assert editor_client.get("/api/v1/admin/audit").status_code == 403
    # but content management is allowed
    assert editor_client.get("/api/v1/admin/productions").status_code == 200


def test_invitation_flow_end_to_end(admin_client, db, mail):
    r = admin_client.post("/api/v1/admin/invitations", json={
        "email": "Yeni.Editor@Example.com", "full_name": "Yeni Editör", "role": "editor"})
    assert r.status_code == 201, r.text
    assert mail[-1]["to"] == "yeni.editor@example.com"
    token = link_token(mail[-1]["body"], "davet")
    # raw token is never stored
    assert db.query(AdminInvitation).filter_by(token_hash=token).count() == 0

    from app.main import app

    with TestClient(app) as anon:
        anon.headers["X-Requested-With"] = "baysahne-admin"
        info = anon.post("/api/v1/admin/auth/invitations/inspect", json={"token": token}).json()
        assert info["email"] == "yeni.editor@example.com" and info["role"] == "editor"
        weak = anon.post("/api/v1/admin/auth/invitations/accept", json={"token": token, "password": "kisa"})
        assert weak.status_code == 400 and weak.json()["error"]["code"] == "weak_password"
        ok = anon.post("/api/v1/admin/auth/invitations/accept", json={"token": token, "password": "Guclu-Parola-2026"})
        assert ok.status_code == 200
        assert anon.get("/api/v1/admin/auth/me").json()["user"]["role"] == "editor"
        reuse = anon.post("/api/v1/admin/auth/invitations/accept", json={"token": token, "password": "Guclu-Parola-2026"})
        assert reuse.status_code == 400


def test_expired_or_revoked_invitation_rejected(admin_client, db, mail):
    admin_client.post("/api/v1/admin/invitations", json={"email": "a@example.com", "full_name": "A", "role": "editor"})
    token = link_token(mail[-1]["body"], "davet")
    inv = db.query(AdminInvitation).filter_by(email="a@example.com").one()
    inv.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert admin_client.post("/api/v1/admin/auth/invitations/inspect", json={"token": token}).status_code == 400

    admin_client.post("/api/v1/admin/invitations", json={"email": "b@example.com", "full_name": "B", "role": "editor"})
    token_b = link_token(mail[-1]["body"], "davet")
    inv_b = db.query(AdminInvitation).filter_by(email="b@example.com").one()
    assert admin_client.delete(f"/api/v1/admin/invitations/{inv_b.id}").status_code == 200
    assert admin_client.post("/api/v1/admin/auth/invitations/inspect", json={"token": token_b}).status_code == 400


def test_password_reset_flow_and_no_enumeration(client, db, mail):
    u = make_user(db)
    client.headers["X-Requested-With"] = "baysahne-admin"
    r1 = client.post("/api/v1/admin/auth/password/forgot", json={"email": u.email})
    r2 = client.post("/api/v1/admin/auth/password/forgot", json={"email": "yok@example.com"})
    assert r1.status_code == r2.status_code == 202 and r1.json() == r2.json()
    assert len(mail) == 1
    token = link_token(mail[0]["body"], "parola-sifirla/yeni")
    assert client.post("/api/v1/admin/auth/password/reset", json={"token": token, "password": "Yeni-Parola-2026"}).status_code == 204
    assert login(client, u.email).status_code == 401
    assert login(client, u.email, "Yeni-Parola-2026").status_code == 200
    assert client.post("/api/v1/admin/auth/password/reset", json={"token": token, "password": "Baska-Parola-2026"}).status_code == 400


def test_deactivating_user_revokes_sessions_immediately(admin_client, db):
    from app.main import app

    editor = make_user(db, AdminRole.editor)
    with TestClient(app) as ec:
        assert login(ec, editor.email).status_code == 200
        assert ec.get("/api/v1/admin/auth/me").status_code == 200
        assert admin_client.post(f"/api/v1/admin/users/{editor.id}/deactivate").status_code == 200
        assert ec.get("/api/v1/admin/auth/me").status_code == 401
        assert login(ec, editor.email).status_code == 401


def test_last_admin_cannot_be_removed_or_demoted(admin_client, db):
    me = admin_client.user
    assert admin_client.post(f"/api/v1/admin/users/{me.id}/deactivate").status_code == 400
    r = admin_client.patch(f"/api/v1/admin/users/{me.id}", json={"role": "editor"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_admin"


def test_logout_invalidates_session(editor_client):
    assert editor_client.post("/api/v1/admin/auth/logout").status_code == 204
    assert editor_client.get("/api/v1/admin/auth/me").status_code == 401


def test_bootstrap_cli_creates_single_admin_invitation(db, capsys):
    from app.cli import bootstrap_admin

    assert bootstrap_admin("ilk@example.com", "İlk Yönetici", force=False) == 0
    out = capsys.readouterr().out
    assert "/davet#" in out
    inv = db.query(AdminInvitation).filter_by(email="ilk@example.com").one()
    assert inv.role == AdminRole.admin
    make_user(db, AdminRole.admin)
    assert bootstrap_admin("ikinci@example.com", "İkinci", force=False) == 1
