from datetime import timedelta
from zoneinfo import ZoneInfo

from app.core.text import utcnow
from app.models import AuditLog, MediaAsset, Production, PublicationStatus
from tests.conftest import mk_production, mk_venue, png_bytes


def upload(client, data=None, name="afis.png", ctype="image/png"):
    return client.post("/api/v1/admin/media", files={"file": (name, data or png_bytes(), ctype)})


def local_in(days: int, hour="20:30") -> str:
    d = (utcnow() + timedelta(days=days)).astimezone(ZoneInfo("Europe/Istanbul"))
    return f"{d:%Y-%m-%d}T{hour}"


def test_create_update_publish_production_with_poster_and_gallery(editor_client, client, db):
    r = editor_client.post("/api/v1/admin/productions", json={
        "title": "Yeni Oyun", "description": "Uzun açıklama", "genres": ["Dram", "dram", "Gerilim"],
        "duration_minutes": 90, "act_count": 2,
        "credits": [{"role": "author", "name": "Yazar Adı"}, {"role": "director", "name": "Yönetmen Adı"}],
        "videos": [{"url": "https://youtu.be/a46Go3Q6X7k", "title": "Fragman"}],
    })
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["slug"] == "yeni-oyun" and p["status"] == "draft"
    assert p["genres"] == ["Dram", "Gerilim"]  # case-insensitive de-duplication
    assert {"field": "poster", "message": "Afiş yok"} in p["issues"]

    # draft is not public
    assert client.get("/api/v1/productions/yeni-oyun").status_code == 404

    poster = upload(editor_client).json()
    assert poster["sm"]["width"] == 480 and poster["lg"]["width"] == 900  # no upscaling
    r = editor_client.put(f"/api/v1/admin/productions/{p['id']}/poster", json={"media_id": poster["id"]})
    assert r.json()["poster"]["id"] == poster["id"]

    g1 = upload(editor_client, png_bytes(800, 533, (10, 10, 10))).json()
    g2 = upload(editor_client, png_bytes(800, 533, (20, 20, 20))).json()
    r = editor_client.post(f"/api/v1/admin/productions/{p['id']}/images", json={"media_ids": [g1["id"], g2["id"]]})
    gallery = r.json()["gallery"]
    assert [g["id"] for g in gallery] == [g1["id"], g2["id"]]
    order = [gallery[1]["image_id"], gallery[0]["image_id"]]
    r = editor_client.put(f"/api/v1/admin/productions/{p['id']}/images/order", json={"image_ids": order})
    assert [g["id"] for g in r.json()["gallery"]] == [g2["id"], g1["id"]]

    preview = editor_client.get(f"/api/v1/admin/productions/{p['id']}/preview").json()
    assert preview["title"] == "Yeni Oyun" and preview["videos"][0]["youtube_id"] == "a46Go3Q6X7k"

    r = editor_client.post(f"/api/v1/admin/productions/{p['id']}/publish", json={"notify": False})
    assert r.status_code == 200 and r.json()["status"] == "published"
    public = client.get("/api/v1/productions/yeni-oyun").json()
    assert public["poster"]["id"] == poster["id"]
    assert [c["label"] for c in public["credits"]] == ["Yazar", "Yönetmen"]
    assert public["duration_label"] == "90 dakika · 2 perde"

    actions = {a.action for a in db.query(AuditLog).all()}
    assert {"production.create", "production.poster_set", "production.gallery_add", "production.publish",
            "media.upload"} <= actions


def test_invalid_production_input_returns_turkish_field_errors(editor_client):
    r = editor_client.post("/api/v1/admin/productions", json={
        "title": "   ", "duration_minutes": 0, "videos": [{"url": "http://insecure.example/video"}]})
    assert r.status_code == 422
    fields = {f["field"]: f["message"] for f in r.json()["error"]["details"]["fields"]}
    assert fields["title"] == "Bu alan zorunludur."
    assert "duration_minutes" in fields
    assert "https" in fields["videos.0.url"]
    unknown = editor_client.post("/api/v1/admin/productions", json={"title": "X", "hacker": True})
    assert unknown.status_code == 422


def test_upload_rejects_non_images_and_oversize(editor_client):
    r = upload(editor_client, b"<svg onload=alert(1)></svg>", "x.svg", "image/svg+xml")
    assert r.status_code == 415
    r = upload(editor_client, b"not really a png", "x.png", "image/png")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_image"


def test_upload_is_deduplicated_and_strips_metadata(editor_client, db):
    data = png_bytes(300, 300)
    a = upload(editor_client, data).json()
    b = upload(editor_client, data).json()
    assert a["id"] == b["id"] and b["duplicate"] is True
    assert db.query(MediaAsset).count() == 1


def test_media_in_use_cannot_be_deleted(editor_client, db):
    p = mk_production(db, "Oyun")
    m = upload(editor_client).json()
    editor_client.put(f"/api/v1/admin/productions/{p.id}/poster", json={"media_id": m["id"]})
    r = editor_client.delete(f"/api/v1/admin/media/{m['id']}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "media_in_use"
    editor_client.delete(f"/api/v1/admin/productions/{p.id}/poster")
    assert editor_client.delete(f"/api/v1/admin/media/{m['id']}").status_code == 204
    assert db.query(MediaAsset).count() == 0


def test_archive_keeps_performance_history_and_blocks_delete(editor_client, db):
    p = mk_production(db, "Arşivlenecek")
    v = mk_venue(db)
    r = editor_client.post("/api/v1/admin/performances", json={
        "production_id": str(p.id), "venue_id": str(v.id), "starts_at_local": local_in(5), "visibility": "published"})
    assert r.status_code == 201, r.text
    assert editor_client.delete(f"/api/v1/admin/productions/{p.id}").status_code == 409
    assert editor_client.post(f"/api/v1/admin/productions/{p.id}/archive").status_code == 200
    rows = editor_client.get("/api/v1/admin/performances", params={"production_id": str(p.id)}).json()
    assert rows["total"] == 1
    db.expire_all()
    assert db.get(Production, p.id).status.value == "archived"


def test_performance_local_time_conversion_and_validation(editor_client, client, db):
    p = mk_production(db, "Saat Testi")
    v = mk_venue(db)
    when = local_in(3, "20:30")
    r = editor_client.post("/api/v1/admin/performances", json={
        "production_id": str(p.id), "venue_id": str(v.id), "starts_at_local": when, "visibility": "published"})
    perf = r.json()
    assert perf["local_time"] == "20:30"
    assert perf["starts_at"].endswith("+00:00") and "T17:30" in perf["starts_at"]  # Istanbul is UTC+3

    past = editor_client.post("/api/v1/admin/performances", json={
        "production_id": str(p.id), "venue_id": str(v.id), "starts_at_local": local_in(-1)})
    assert past.status_code == 400 and past.json()["error"]["code"] == "past_datetime"
    bad = editor_client.post("/api/v1/admin/performances", json={
        "production_id": str(p.id), "venue_id": str(v.id), "starts_at_local": "31.12.2026 20:00"})
    assert bad.status_code == 422


def test_schedule_conflicts_require_confirmation(editor_client, db):
    a = mk_production(db, "A")
    b = mk_production(db, "B")
    v = mk_venue(db)
    when = local_in(4, "20:00")
    base = {"venue_id": str(v.id), "visibility": "published"}
    assert editor_client.post("/api/v1/admin/performances", json={
        **base, "production_id": str(a.id), "starts_at_local": when}).status_code == 201
    r = editor_client.post("/api/v1/admin/performances", json={
        **base, "production_id": str(b.id), "starts_at_local": local_in(4, "21:00")})
    assert r.status_code == 409
    assert r.json()["error"]["details"]["conflicts"][0]["reason"] == "same_venue"
    r = editor_client.post("/api/v1/admin/performances", json={
        **base, "production_id": str(b.id), "starts_at_local": local_in(4, "21:00"), "allow_conflict": True})
    assert r.status_code == 201


def test_published_performance_date_change_requires_reschedule(editor_client, client, db):
    p = mk_production(db, "Erteleme")
    v = mk_venue(db)
    perf = editor_client.post("/api/v1/admin/performances", json={
        "production_id": str(p.id), "venue_id": str(v.id), "starts_at_local": local_in(5),
        "visibility": "published"}).json()
    r = editor_client.patch(f"/api/v1/admin/performances/{perf['id']}", json={"starts_at_local": local_in(6)})
    assert r.status_code == 409 and r.json()["error"]["code"] == "use_reschedule"

    r = editor_client.post(f"/api/v1/admin/performances/{perf['id']}/reschedule",
                           json={"starts_at_local": local_in(6, "19:00"), "notify": False})
    assert r.status_code == 200
    body = r.json()
    assert body["is_rescheduled"] and body["rescheduled_from_local"]["local_time"] == "20:30"
    public = client.get("/api/v1/performances").json()["items"][0]
    assert public["is_rescheduled"] and public["local_time"] == "19:00"


def test_cancel_and_restore(editor_client, client, db):
    p = mk_production(db, "İptal")
    v = mk_venue(db)
    perf = editor_client.post("/api/v1/admin/performances", json={
        "production_id": str(p.id), "venue_id": str(v.id), "starts_at_local": local_in(2),
        "visibility": "published"}).json()
    r = editor_client.post(f"/api/v1/admin/performances/{perf['id']}/cancel",
                           json={"cancellation_note": "Hastalık nedeniyle", "notify": False})
    assert r.json()["is_cancelled"] is True
    assert editor_client.post(f"/api/v1/admin/performances/{perf['id']}/cancel", json={}).status_code == 409
    assert editor_client.delete(f"/api/v1/admin/performances/{perf['id']}").status_code == 409  # history kept
    public = client.get("/api/v1/performances").json()["items"]
    assert public[0]["is_cancelled"] and public[0]["cancellation_note"] == "Hastalık nedeniyle"
    r = editor_client.post(f"/api/v1/admin/performances/{perf['id']}/restore")
    assert r.json()["is_cancelled"] is False


def test_venue_management(editor_client, db):
    r = editor_client.post("/api/v1/admin/venues", json={"name": "Yeni Salon", "city": "Adana",
                                                         "maps_url": "https://maps.example/x"})
    assert r.status_code == 201
    vid = r.json()["id"]
    assert editor_client.put(f"/api/v1/admin/venues/{vid}", json={"name": "Yeni Salon 2", "timezone": "Mars/Base"}
                             ).status_code == 422
    assert editor_client.put(f"/api/v1/admin/venues/{vid}", json={"name": "Yeni Salon 2"}).json()["name"] == "Yeni Salon 2"
    assert editor_client.delete(f"/api/v1/admin/venues/{vid}").status_code == 204


def test_articles_publication(editor_client, client):
    a = editor_client.post("/api/v1/admin/articles", json={"title": "Sezon Açılışı", "body": "Merhaba seyirci."}).json()
    assert client.get("/api/v1/articles").json()["total"] == 0
    editor_client.post(f"/api/v1/admin/articles/{a['id']}/publish", json={})
    items = client.get("/api/v1/articles").json()["items"]
    assert items[0]["slug"] == "sezon-acilisi"
    assert client.get("/api/v1/articles/sezon-acilisi").json()["body"] == "Merhaba seyirci."
    future = (utcnow() + timedelta(days=2)).isoformat()
    editor_client.post(f"/api/v1/admin/articles/{a['id']}/publish", json={"published_at": future})
    assert client.get("/api/v1/articles").json()["total"] == 0  # scheduled, not yet visible


def test_dashboard_reflects_database(editor_client, db):
    mk_production(db, "Yayında")
    mk_production(db, "Taslak", status=PublicationStatus.draft)
    d = editor_client.get("/api/v1/admin/dashboard").json()
    assert d["productions"] == {"total": 2, "published": 1, "draft": 1, "archived": 0}
    assert d["performances"]["upcoming"] == 0
    assert any(t["kind"] == "no_schedule" for t in d["tasks"])
    assert len(d["incomplete_productions"]) == 2
