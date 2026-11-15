"""The brief's 10-step acceptance workflow, end to end through the HTTP API with the fake push provider."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.core.text import utcnow
from app.main import app
from app.models import AdminRole, JobStatus, NotificationCategory, NotificationJob
from app.notifications import engine
from tests.conftest import link_token, login, make_user, mk_venue, png_bytes


def test_full_workflow(db, mail, push):
    # 1. A privileged administrator can access the administration panel.
    admin_user = make_user(db, AdminRole.admin)
    admin = TestClient(app)
    assert login(admin, admin_user.email).status_code == 200
    assert admin.get("/api/v1/admin/dashboard").status_code == 200

    # The admin invites an editor, who accepts the invitation.
    admin.post("/api/v1/admin/invitations", json={"email": "editor@example.com", "full_name": "Editör", "role": "editor"})
    token = link_token(mail[-1]["body"], "davet")
    editor = TestClient(app, headers={"X-Requested-With": "baysahne-admin"})
    assert editor.post("/api/v1/admin/auth/invitations/accept",
                       json={"token": token, "password": "Kulis-Parola-2026"}).status_code == 200

    # Two audience devices have opted in to notifications.
    public = TestClient(app)
    for i in range(2):
        assert public.post("/api/v1/devices", json={
            "installation_id": f"e2e-install-{i:04d}-0000", "platform": "ios" if i else "android",
            "permission": "granted", "push_token": f"ExponentPushToken[e2e-device-{i:04d}-xyz]"}).json() == {"active": True}

    # 2. The editor creates a production. 3. Uploads a poster and enters details.
    p = editor.post("/api/v1/admin/productions", json={
        "title": "Uçurtma Avcısı", "description": "Bir dostluk hikâyesi.", "genres": ["Dram"],
        "duration_minutes": 100, "credits": [{"role": "director", "name": "Yönetmen Adı"}]}).json()
    poster = editor.post("/api/v1/admin/media", files={"file": ("afis.jpg", png_bytes(fmt="JPEG"), "image/jpeg")}).json()
    editor.put(f"/api/v1/admin/productions/{p['id']}/poster", json={"media_id": poster["id"]})
    assert public.get(f"/api/v1/productions/{p['slug']}").status_code == 404  # still a draft

    # 4. The editor publishes the production (with the new-production notification).
    r = editor.post(f"/api/v1/admin/productions/{p['id']}/publish", json={"notify": True}).json()
    assert r["notification_job_id"]

    # 5. The published production appears in the mobile application's API.
    detail = public.get(f"/api/v1/productions/{p['slug']}").json()
    assert detail["poster"]["id"] == poster["id"] and detail["performances"] == []
    assert p["slug"] in [x["slug"] for x in public.get("/api/v1/productions").json()["items"]]

    # 6. The editor creates a performance with a real date, time and venue.
    venue = mk_venue(db, "Baysahne Performans Atölyesi")
    day = (utcnow() + timedelta(days=4)).astimezone(ZoneInfo("Europe/Istanbul"))
    perf = editor.post("/api/v1/admin/performances", json={
        "production_id": p["id"], "venue_id": str(venue.id), "starts_at_local": f"{day:%Y-%m-%d}T20:30",
        "visibility": "published"}).json()

    # 7. The performance appears in the public schedule.
    sched = public.get("/api/v1/performances").json()["items"]
    assert [s["id"] for s in sched] == [perf["id"]] and sched[0]["local_time"] == "20:30"

    # 8. The backend created the appropriate notification jobs.
    jobs = {j.category: j for j in db.query(NotificationJob).all()}
    assert set(jobs) == {NotificationCategory.new_production, NotificationCategory.performance_reminder}

    # 9. The scheduler processes the jobs without duplicate sends (several ticks, including at reminder time).
    now = utcnow()
    for t in (now, now + timedelta(minutes=1)):
        engine.run_once(db, push, t)
    assert len(push.sent) == 2  # new-production broadcast to 2 devices, once
    reminder_time = jobs[NotificationCategory.performance_reminder].scheduled_for + timedelta(seconds=1)
    engine.run_once(db, push, reminder_time)
    engine.run_once(db, push, reminder_time + timedelta(minutes=5))
    assert len(push.sent) == 4  # + one reminder per device
    assert sorted(m.title for m in push.sent) == sorted(
        ["Yeni oyun: Uçurtma Avcısı"] * 2 + ["Hatırlatma: Uçurtma Avcısı"] * 2)

    # 10. A reschedule, then a cancellation, are reflected in the app and the notification workflow.
    later = day + timedelta(days=2)
    editor.post(f"/api/v1/admin/performances/{perf['id']}/reschedule",
                json={"starts_at_local": f"{later:%Y-%m-%d}T19:00", "notify": True})
    s = public.get("/api/v1/performances").json()["items"][0]
    assert s["is_rescheduled"] and s["local_time"] == "19:00"
    editor.post(f"/api/v1/admin/performances/{perf['id']}/cancel", json={"notify": True,
                                                                         "cancellation_note": "Hastalık nedeniyle"})
    s = public.get("/api/v1/performances").json()["items"][0]
    assert s["is_cancelled"] and s["cancellation_note"] == "Hastalık nedeniyle"
    assert public.get(f"/api/v1/productions/{p['slug']}").json()["upcoming_count"] == 0

    engine.run_once(db, push, reminder_time + timedelta(minutes=10))
    engine.run_once(db, push, reminder_time + timedelta(minutes=11))
    db.expire_all()
    by_cat = {}
    for j in db.query(NotificationJob).all():
        by_cat.setdefault(j.category, []).append(j)
    # The reschedule notice was superseded by the cancellation before it went out; only the cancellation is sent.
    assert [j.status for j in by_cat[NotificationCategory.performance_rescheduled]] == [JobStatus.cancelled]
    assert [j.status for j in by_cat[NotificationCategory.performance_cancelled]] == [JobStatus.sent]
    assert all(j.status != JobStatus.pending for j in by_cat[NotificationCategory.performance_reminder])
    titles = [m.title for m in push.sent]
    assert titles.count("Program değişikliği: Uçurtma Avcısı") == 2
    assert len(push.sent) == 6
