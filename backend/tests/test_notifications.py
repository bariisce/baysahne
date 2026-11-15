from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core.text import utcnow
from app.models import (
    DeliveryStatus,
    JobStatus,
    NotificationCategory,
    NotificationDelivery,
    NotificationJob,
    NotificationPolicy,
    PerformanceStatus,
    PublicationStatus,
    PushDevice,
    Visibility,
)
from app.notifications import engine
from tests.conftest import mk_performance, mk_production, mk_venue


def token(i) -> str:
    return f"ExponentPushToken[test-device-{i:04d}-abcdef]"


def register(client, i, permission="granted", platform="android", installation=None):
    return client.post("/api/v1/devices", json={
        "installation_id": installation or f"install-{i:04d}-0000-0000",
        "platform": platform, "permission": permission,
        "push_token": token(i) if permission == "granted" else None, "app_version": "1.0.0", "locale": "tr-TR"})


def devices(client, n):
    for i in range(n):
        assert register(client, i).status_code == 200


def run(db, push, now=None):
    return engine.run_once(db, push, now)


def jobs(db, category=None):
    q = select(NotificationJob)
    if category:
        q = q.where(NotificationJob.category == category)
    return db.scalars(q).all()


def local_in(days: int, hour="20:30") -> str:
    d = (utcnow() + timedelta(days=days)).astimezone(ZoneInfo("Europe/Istanbul"))
    return f"{d:%Y-%m-%d}T{hour}"


# ---------------------------------------------------------------- device registration


def test_device_registration_is_idempotent_and_never_echoes_token(client, db):
    r1 = register(client, 1)
    r2 = register(client, 1)
    assert r1.json() == r2.json() == {"active": True}
    assert "ExponentPushToken" not in r1.text
    assert db.query(PushDevice).count() == 1


def test_token_refresh_and_token_moving_between_installations(client, db):
    register(client, 1, installation="install-aaaa-1111-0000")
    # Same installation gets a new token (token refresh)
    client.post("/api/v1/devices", json={"installation_id": "install-aaaa-1111-0000", "platform": "ios",
                                         "permission": "granted", "push_token": token(2)})
    d = db.query(PushDevice).one()
    assert d.push_token == token(2) and d.platform.value == "ios"
    # Reinstall: new installation id, same token → old row detached, no duplicate active registration
    client.post("/api/v1/devices", json={"installation_id": "install-bbbb-2222-0000", "platform": "ios",
                                         "permission": "granted", "push_token": token(2)})
    db.expire_all()
    active = db.query(PushDevice).filter_by(is_active=True).all()
    assert [a.installation_id for a in active] == ["install-bbbb-2222-0000"]
    old = db.query(PushDevice).filter_by(installation_id="install-aaaa-1111-0000").one()
    assert old.push_token is None and old.deactivation_reason == "token_moved"


def test_permission_revocation_and_unregister_deactivate(client, db):
    register(client, 1)
    register(client, 1, permission="denied", installation="install-0001-0000-0000")
    d = db.query(PushDevice).one()
    assert d.is_active is False and d.deactivation_reason == "permission_denied"
    register(client, 1)
    assert client.delete("/api/v1/devices/install-0001-0000-0000").status_code == 204
    db.expire_all()
    assert db.query(PushDevice).one().deactivation_reason == "unregistered"


def test_invalid_device_payloads_rejected(client):
    bad_token = client.post("/api/v1/devices", json={"installation_id": "install-0001-0000-0000",
                                                     "platform": "android", "permission": "granted",
                                                     "push_token": "not-a-token"})
    assert bad_token.status_code == 422
    bad_platform = client.post("/api/v1/devices", json={"installation_id": "install-0001-0000-0000",
                                                        "platform": "windows", "permission": "granted"})
    assert bad_platform.status_code == 422


# ---------------------------------------------------------------- new production


def test_new_production_notification_once_only(editor_client, client, db, push):
    devices(client, 3)
    p = editor_client.post("/api/v1/admin/productions", json={"title": "Yeni Gösteri"}).json()
    r = editor_client.post(f"/api/v1/admin/productions/{p['id']}/publish", json={"notify": True})
    assert r.json()["notification_job_id"]
    run(db, push)
    assert len(push.sent) == 3
    assert push.sent[0].title == "Yeni oyun: Yeni Gösteri"
    assert push.sent[0].data == {"type": "production", "production_slug": "yeni-gosteri"}

    # unpublish + republish with notify: no second broadcast
    editor_client.post(f"/api/v1/admin/productions/{p['id']}/unpublish")
    r = editor_client.post(f"/api/v1/admin/productions/{p['id']}/publish", json={"notify": True})
    assert r.json()["notification_job_id"] is None
    run(db, push)
    run(db, push)
    assert len(push.sent) == 3
    assert len(jobs(db, NotificationCategory.new_production)) == 1


def test_draft_content_never_notifies(editor_client, client, db, push):
    devices(client, 2)
    p = editor_client.post("/api/v1/admin/productions", json={"title": "Taslak"}).json()
    v = mk_venue(db)
    editor_client.post("/api/v1/admin/performances", json={
        "production_id": p["id"], "venue_id": str(v.id), "starts_at_local": local_in(1, "23:30"),
        "visibility": "published"})
    run(db, push)
    assert push.sent == [] and jobs(db) == []


def test_unpublish_before_dispatch_cancels_job(editor_client, client, db, push):
    devices(client, 1)
    p = editor_client.post("/api/v1/admin/productions", json={"title": "Geri Alınan"}).json()
    editor_client.post(f"/api/v1/admin/productions/{p['id']}/publish", json={"notify": True})
    editor_client.post(f"/api/v1/admin/productions/{p['id']}/unpublish")
    run(db, push)
    assert push.sent == []
    assert jobs(db)[0].status == JobStatus.cancelled and jobs(db)[0].cancel_reason == "production_not_published"


# ---------------------------------------------------------------- reminders


def test_reminder_planned_once_and_sent_once(client, db, push):
    devices(client, 2)
    v = mk_venue(db)
    p = mk_production(db, "Hatırlatma")
    perf = mk_performance(db, p, v, hours=30)
    now = utcnow()
    run(db, push, now)
    run(db, push, now + timedelta(minutes=1))
    reminder = jobs(db, NotificationCategory.performance_reminder)
    assert len(reminder) == 1
    assert reminder[0].status == JobStatus.pending
    assert abs((reminder[0].scheduled_for - (perf.starts_at - timedelta(hours=24))).total_seconds()) < 1
    assert push.sent == []

    later = perf.starts_at - timedelta(hours=24) + timedelta(seconds=5)
    run(db, push, later)
    run(db, push, later + timedelta(minutes=1))  # scheduler re-run / restart
    assert len(push.sent) == 2
    assert push.sent[0].title == "Hatırlatma: Hatırlatma"
    db.expire_all()
    assert jobs(db, NotificationCategory.performance_reminder)[0].status == JobStatus.sent


def test_reminder_lead_times_are_configurable(admin_client, client, db, push):
    devices(client, 1)
    v = mk_venue(db)
    p = mk_production(db, "Çoklu")
    mk_performance(db, p, v, hours=50)
    r = admin_client.put("/api/v1/admin/notifications/policy", json={
        "reminder_lead_minutes": [2880, 120], "max_per_device_per_day": 5, "broadcast_cooldown_minutes": 0})
    assert r.status_code == 200
    run(db, push)
    leads = sorted(j.lead_minutes for j in jobs(db, NotificationCategory.performance_reminder))
    assert leads == [120, 2880]

    # removing a lead time cancels its pending job
    admin_client.put("/api/v1/admin/notifications/policy", json={
        "reminder_lead_minutes": [120], "max_per_device_per_day": 5, "broadcast_cooldown_minutes": 0})
    db.expire_all()
    by_lead = {j.lead_minutes: j for j in jobs(db, NotificationCategory.performance_reminder)}
    assert by_lead[2880].status == JobStatus.cancelled and by_lead[2880].cancel_reason == "lead_time_removed"
    assert by_lead[120].status == JobStatus.pending


def test_late_reminders_are_skipped_not_sent_late(client, db, push):
    devices(client, 1)
    v = mk_venue(db)
    p = mk_production(db, "Geç")
    mk_performance(db, p, v, hours=3)  # created after its 24h reminder time
    run(db, push)
    assert jobs(db, NotificationCategory.performance_reminder) == []


def test_unpublished_or_draft_performance_gets_no_reminder(client, db, push):
    devices(client, 1)
    v = mk_venue(db)
    mk_performance(db, mk_production(db, "Taslak Temsil"), v, hours=30, visibility=Visibility.draft)
    mk_performance(db, mk_production(db, "Taslak Oyun", status=PublicationStatus.draft), v, hours=30)
    run(db, push)
    assert jobs(db) == []


# ---------------------------------------------------------------- cancellation / reschedule


def test_cancellation_cancels_reminders_and_notifies_once(editor_client, client, db, push):
    devices(client, 2)
    v = mk_venue(db)
    p = mk_production(db, "İptal Edilen")
    perf = editor_client.post("/api/v1/admin/performances", json={
        "production_id": str(p.id), "venue_id": str(v.id), "starts_at_local": local_in(2),
        "visibility": "published"}).json()
    run(db, push)
    assert len(jobs(db, NotificationCategory.performance_reminder)) == 1

    r = editor_client.post(f"/api/v1/admin/performances/{perf['id']}/cancel", json={"notify": True})
    assert r.json()["notification_job_id"]
    run(db, push)
    run(db, push)
    db.expire_all()
    assert jobs(db, NotificationCategory.performance_reminder)[0].status == JobStatus.cancelled
    cancel_jobs = jobs(db, NotificationCategory.performance_cancelled)
    assert len(cancel_jobs) == 1 and cancel_jobs[0].status == JobStatus.sent
    assert len(push.sent) == 2
    assert push.sent[0].title == "Program değişikliği: İptal Edilen"
    assert "iptal edildi" in push.sent[0].body


def test_never_announced_performance_cancel_does_not_notify(editor_client, client, db, push):
    devices(client, 1)
    v = mk_venue(db)
    p = mk_production(db, "Duyurulmamış")
    perf = editor_client.post("/api/v1/admin/performances", json={
        "production_id": str(p.id), "venue_id": str(v.id), "starts_at_local": local_in(2)}).json()  # draft
    r = editor_client.post(f"/api/v1/admin/performances/{perf['id']}/cancel", json={"notify": True})
    assert r.json()["notification_job_id"] is None


def test_reschedule_replaces_reminder_and_sends_update(editor_client, client, db, push):
    devices(client, 1)
    v = mk_venue(db)
    p = mk_production(db, "Ertelenen")
    perf = editor_client.post("/api/v1/admin/performances", json={
        "production_id": str(p.id), "venue_id": str(v.id), "starts_at_local": local_in(3, "20:00"),
        "visibility": "published"}).json()
    run(db, push)
    old = jobs(db, NotificationCategory.performance_reminder)
    assert len(old) == 1

    r = editor_client.post(f"/api/v1/admin/performances/{perf['id']}/reschedule",
                           json={"starts_at_local": local_in(5, "21:00"), "notify": True})
    assert r.status_code == 200 and r.json()["notification_job_id"]
    run(db, push)
    db.expire_all()
    reminders = {j.id: j for j in jobs(db, NotificationCategory.performance_reminder)}
    assert reminders[old[0].id].status == JobStatus.cancelled
    assert reminders[old[0].id].cancel_reason == "performance_rescheduled"
    fresh = [j for j in reminders.values() if j.status == JobStatus.pending]
    assert len(fresh) == 1 and fresh[0].data["starts_at"] != old[0].data["starts_at"]
    assert len(push.sent) == 1
    assert push.sent[0].title == "Yeni tarih: Ertelenen"
    assert "21:00" in push.sent[0].body and "20:00" in push.sent[0].body

    # a second reschedule supersedes nothing already sent, and creates exactly one more update
    editor_client.post(f"/api/v1/admin/performances/{perf['id']}/reschedule",
                       json={"starts_at_local": local_in(6, "21:00"), "notify": True})
    run(db, push)
    assert len(jobs(db, NotificationCategory.performance_rescheduled)) == 2
    assert len(push.sent) == 2


# ---------------------------------------------------------------- reliability


def test_provider_outage_retries_with_backoff_without_duplicates(editor_client, client, db, push):
    devices(client, 3)
    p = editor_client.post("/api/v1/admin/productions", json={"title": "Kesinti"}).json()
    editor_client.post(f"/api/v1/admin/productions/{p['id']}/publish", json={"notify": True})
    push.fail_next_requests = 1
    now = utcnow()
    run(db, push, now)
    db.expire_all()
    job = jobs(db)[0]
    assert job.status == JobStatus.pending and job.attempts == 1 and "Sağlayıcı" in job.last_error
    assert db.query(NotificationDelivery).count() == 0  # reservations released
    run(db, push, now + timedelta(seconds=30))  # before backoff elapses: nothing
    assert push.sent == []
    run(db, push, now + timedelta(minutes=3))
    run(db, push, now + timedelta(minutes=10))
    assert len(push.sent) == 3
    assert len({m.to for m in push.sent}) == 3


def test_job_fails_after_max_attempts_and_admin_can_retry(editor_client, admin_client, client, db, push):
    devices(client, 1)
    p = editor_client.post("/api/v1/admin/productions", json={"title": "Başarısız"}).json()
    editor_client.post(f"/api/v1/admin/productions/{p['id']}/publish", json={"notify": True})
    push.fail_next_requests = 100
    t = utcnow()
    for i in range(8):
        run(db, push, t + timedelta(hours=i))
    db.expire_all()
    job = jobs(db)[0]
    assert job.status == JobStatus.failed and job.attempts == 5
    push.fail_next_requests = 0
    assert admin_client.post(f"/api/v1/admin/notifications/jobs/{job.id}/retry").status_code == 200
    run(db, push)
    assert len(push.sent) == 1


def test_interrupted_send_is_not_repeated(client, db, push):
    """Simulate a worker crash after reserving deliveries but before recording the provider result."""
    devices(client, 2)
    p = mk_production(db, "Çökme")
    job = engine.on_production_published(db, p)
    db.commit()
    dev_ids = [d.id for d in db.query(PushDevice).all()]
    job.status, job.locked_at, job.attempts = JobStatus.processing, utcnow() - timedelta(hours=1), 1
    db.add(NotificationDelivery(job_id=job.id, device_id=dev_ids[0], status=DeliveryStatus.queued))
    db.commit()
    run(db, push)
    db.expire_all()
    assert [m.to for m in push.sent] == [db.get(PushDevice, dev_ids[1]).push_token]
    interrupted = db.query(NotificationDelivery).filter_by(device_id=dev_ids[0]).one()
    assert interrupted.error_code == "interrupted"


def test_device_not_registered_deactivates_token(client, db, push):
    devices(client, 2)
    push.device_errors[token(0)] = "DeviceNotRegistered"
    p = mk_production(db, "Geçersiz Anahtar")
    engine.on_production_published(db, p)
    db.commit()
    run(db, push)
    db.expire_all()
    dead = db.query(PushDevice).filter_by(push_token=token(0)).one()
    assert dead.is_active is False and dead.deactivation_reason == "device_not_registered"
    assert jobs(db)[0].stats == {"targeted": 2, "ok": 1, "error": 1, "rate_limited": 0}


def test_receipts_deactivate_unregistered_devices(client, db, push):
    devices(client, 1)
    push.receipt_errors[token(0)] = "DeviceNotRegistered"
    engine.on_production_published(db, mk_production(db, "Makbuz"))
    db.commit()
    now = utcnow()
    run(db, push, now)
    run(db, push, now + timedelta(minutes=20))
    db.expire_all()
    assert db.query(PushDevice).one().is_active is False


def test_frequency_cap_limits_routine_but_not_schedule_changes(client, db, push):
    devices(client, 1)
    db.get(NotificationPolicy, 1).max_per_device_per_day = 1
    db.get(NotificationPolicy, 1).broadcast_cooldown_minutes = 0
    db.commit()
    for title in ("Bir", "İki"):
        engine.on_production_published(db, mk_production(db, title))
        db.commit()
        run(db, push)
    assert len(push.sent) == 1
    assert db.query(NotificationDelivery).filter_by(status=DeliveryStatus.rate_limited).count() == 1

    v = mk_venue(db)
    perf = mk_performance(db, mk_production(db, "Önemli"), v, hours=5)
    perf.status = PerformanceStatus.cancelled
    db.commit()
    engine.on_performance_cancelled(db, perf)
    db.commit()
    run(db, push)
    assert len(push.sent) == 2  # cancellations bypass the cap


def test_broadcast_cooldown_delays_second_new_production(client, db, push):
    devices(client, 1)
    db.get(NotificationPolicy, 1).max_per_device_per_day = 10
    db.commit()
    now = utcnow()
    engine.on_production_published(db, mk_production(db, "İlk"))
    db.commit()
    run(db, push, now + timedelta(seconds=2))
    engine.on_production_published(db, mk_production(db, "İkinci"))
    db.commit()
    run(db, push, now + timedelta(minutes=5))
    assert len(push.sent) == 1
    run(db, push, now + timedelta(minutes=62))
    assert len(push.sent) == 2


def test_disabling_category_cancels_pending(admin_client, client, db, push):
    devices(client, 1)
    v = mk_venue(db)
    mk_performance(db, mk_production(db, "Kapalı"), v, hours=30)
    run(db, push)
    cat = admin_client.get("/api/v1/admin/notifications/settings").json()["categories"][1]
    assert cat["category"] == "performance_reminder"
    r = admin_client.put("/api/v1/admin/notifications/categories/performance_reminder",
                         json={**{k: cat[k] for k in ("title_template", "body_template")}, "enabled": False})
    assert r.status_code == 200
    db.expire_all()
    assert jobs(db)[0].status == JobStatus.cancelled and jobs(db)[0].cancel_reason == "category_disabled"


@pytest.mark.parametrize("template", ["{title.__class__}", "{nope}", "{title!r}", "{title:>10}", "{title"])
def test_unsafe_templates_rejected(admin_client, template):
    r = admin_client.put("/api/v1/admin/notifications/categories/new_production",
                         json={"enabled": True, "title_template": template, "body_template": "x"})
    assert r.status_code == 422


def test_template_preview_and_edit_applies_to_next_send(admin_client, client, db, push):
    r = admin_client.post("/api/v1/admin/notifications/preview",
                          json={"category": "performance_reminder", "title_template": "Yarın: {title}"})
    assert r.json() == {"title": "Yarın: Örnek Oyun", "body": "18 Ekim Pazar, saat 20:30 · Örnek Salon",
                        "source": "sample"}
    admin_client.put("/api/v1/admin/notifications/categories/new_production",
                     json={"enabled": True, "title_template": "Repertuvarda: {title}", "body_template": "{genre}"})
    devices(client, 1)
    engine.on_production_published(db, mk_production(db, "Şablon", genres=["Komedi"]))
    db.commit()
    run(db, push)
    assert (push.sent[0].title, push.sent[0].body) == ("Repertuvarda: Şablon", "Komedi")


def test_jobs_visible_to_admin_panel(editor_client, client, db, push):
    devices(client, 1)
    p = editor_client.post("/api/v1/admin/productions", json={"title": "Liste"}).json()
    editor_client.post(f"/api/v1/admin/productions/{p['id']}/publish", json={"notify": True})
    run(db, push)
    listing = editor_client.get("/api/v1/admin/notifications/jobs").json()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["status"] == "sent" and item["stats"]["ok"] == 1 and item["category_label"] == "Yeni oyun"
    detail = editor_client.get(f"/api/v1/admin/notifications/jobs/{item['id']}").json()
    assert detail["error_breakdown"] == []
    # editors can view but not cancel/retry
    assert editor_client.post(f"/api/v1/admin/notifications/jobs/{item['id']}/retry").status_code == 403


