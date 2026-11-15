from datetime import timedelta

from app.core.text import utcnow
from app.models import PerformanceStatus, PublicationStatus, Visibility
from tests.conftest import mk_performance, mk_production, mk_venue


def test_only_published_productions_are_listed(client, db):
    pub = mk_production(db, "Yayındaki Oyun")
    mk_production(db, "Taslak Oyun", status=PublicationStatus.draft)
    mk_production(db, "Arşiv Oyunu", status=PublicationStatus.archived)

    r = client.get("/api/v1/productions")
    assert r.status_code == 200
    titles = [p["title"] for p in r.json()["items"]]
    assert titles == ["Yayındaki Oyun"]

    assert client.get(f"/api/v1/productions/{pub.slug}").status_code == 200


def test_unpublished_detail_is_404(client, db):
    draft = mk_production(db, "Gizli", status=PublicationStatus.draft)
    archived = mk_production(db, "Eski", status=PublicationStatus.archived)
    for p in (draft, archived):
        r = client.get(f"/api/v1/productions/{p.slug}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"


def test_production_visible_without_any_performance(client, db):
    p = mk_production(db, "Programsız Oyun")
    body = client.get(f"/api/v1/productions/{p.slug}").json()
    assert body["performances"] == []
    assert body["next_performance"] is None
    assert body["upcoming_count"] == 0


def test_schedule_is_chronological_and_respects_visibility(client, db):
    v = mk_venue(db)
    a = mk_production(db, "A Oyunu")
    b = mk_production(db, "B Oyunu")
    hidden_prod = mk_production(db, "Taslak", status=PublicationStatus.draft)
    p3 = mk_performance(db, a, v, hours=72)
    p1 = mk_performance(db, b, v, hours=24)
    p2 = mk_performance(db, a, v, hours=48)
    mk_performance(db, a, v, hours=96, visibility=Visibility.draft)  # draft performance
    mk_performance(db, hidden_prod, v, hours=30)  # unpublished production
    past = mk_performance(db, a, v, hours=5)
    past.starts_at = utcnow() - timedelta(hours=2)
    db.commit()

    items = client.get("/api/v1/performances").json()["items"]
    assert [i["id"] for i in items] == [str(p1.id), str(p2.id), str(p3.id)]
    first = items[0]
    assert first["production"]["title"] == "B Oyunu"
    assert first["venue"]["name"] == "Ana Salon"
    assert first["local_time"] and first["local_weekday"]
    assert first["starts_at"].endswith("+00:00")


def test_cancelled_performance_is_flagged_not_available(client, db):
    v = mk_venue(db)
    p = mk_production(db, "İptalli Oyun")
    live = mk_performance(db, p, v, hours=24)
    cancelled = mk_performance(db, p, v, hours=48, status=PerformanceStatus.cancelled,
                               cancellation_note="Teknik nedenlerle")

    sched = client.get("/api/v1/performances").json()["items"]
    by_id = {i["id"]: i for i in sched}
    assert by_id[str(cancelled.id)]["is_cancelled"] is True
    assert by_id[str(cancelled.id)]["cancellation_note"] == "Teknik nedenlerle"
    assert by_id[str(live.id)]["is_cancelled"] is False

    only_active = client.get("/api/v1/performances", params={"include_cancelled": "false"}).json()["items"]
    assert [i["id"] for i in only_active] == [str(live.id)]

    detail = client.get(f"/api/v1/productions/{p.slug}").json()
    assert detail["upcoming_count"] == 1  # cancelled does not count as available
    assert detail["next_performance"]["id"] == str(live.id)

    home = client.get("/api/v1/home").json()
    assert [u["id"] for u in home["upcoming"]] == [str(live.id)]


def test_catalog_filters_and_turkish_search(client, db):
    v = mk_venue(db)
    muf = mk_production(db, "Müfettiş", genres=["Komedi"])
    mk_production(db, "Sefiller", genres=["Dram"], on_stage=True)
    mk_performance(db, muf, v, hours=30)

    def titles(**params):
        return [p["title"] for p in client.get("/api/v1/productions", params=params).json()["items"]]

    assert titles(q="mufettis") == ["Müfettiş"]
    assert titles(q="MÜFETTİŞ") == ["Müfettiş"]
    assert titles(genre="Dram") == ["Sefiller"]
    assert titles(has_upcoming="true") == ["Müfettiş"]
    assert titles(has_upcoming="false") == ["Sefiller"]
    assert titles(on_stage="true") == ["Sefiller"]
    assert client.get("/api/v1/genres").json()["items"] == ["Dram", "Komedi"]


def test_pagination_and_invalid_params(client, db):
    for i in range(5):
        mk_production(db, f"Oyun {i}")
    r = client.get("/api/v1/productions", params={"page": 2, "page_size": 2}).json()
    assert r["total"] == 5 and len(r["items"]) == 2 and r["page"] == 2
    bad = client.get("/api/v1/productions", params={"page_size": 1000})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "validation_error"


def test_home_is_useful_without_performances(client, db):
    mk_production(db, "Sahnedeki", on_stage=True)
    home = client.get("/api/v1/home").json()
    assert home["upcoming"] == []
    assert home["featured_source"] == "on_stage"
    assert [p["title"] for p in home["featured"]] == ["Sahnedeki"]
    assert [p["title"] for p in home["new_productions"]] == ["Sahnedeki"]


def test_home_repertoire_follows_the_editors_order(client, db):
    # Created in an order unrelated to the wanted one; catalogue order (sort_order) must not matter either.
    mk_production(db, "Frankenstein", home_order=5, sort_order=0)
    mk_production(db, "Antigone", sort_order=10)
    mk_production(db, "Notre Dame'ın Kamburu", home_order=4, sort_order=50)
    mk_production(db, "Hayvan Çiftliği", home_order=3, sort_order=80)
    mk_production(db, "Bir Yaz Gecesi Rüyası", home_order=1, sort_order=60)
    mk_production(db, "Sefiller", home_order=2, sort_order=70)
    mk_production(db, "Taslak", home_order=1, status=PublicationStatus.draft)

    home = client.get("/api/v1/home").json()
    assert [p["title"] for p in home["new_productions"]] == [
        "Bir Yaz Gecesi Rüyası", "Sefiller", "Hayvan Çiftliği", "Notre Dame'ın Kamburu", "Frankenstein",
    ]


def test_editor_sets_and_clears_the_home_position(editor_client, client, db):
    p = mk_production(db, "Sefiller")
    other = mk_production(db, "Antigone")
    url = f"/api/v1/admin/productions/{p.id}"

    r = editor_client.patch(url, json={"home_order": 1})
    assert r.status_code == 200 and r.json()["home_order"] == 1
    assert [x["title"] for x in client.get("/api/v1/home").json()["new_productions"]] == ["Sefiller"]

    assert editor_client.patch(url, json={"home_order": 0}).status_code == 422
    r = editor_client.patch(url, json={"home_order": None})
    assert r.status_code == 200 and r.json()["home_order"] is None
    # Nothing curated any more: the strip falls back to recently published productions.
    titles = {x["title"] for x in client.get("/api/v1/home").json()["new_productions"]}
    assert titles == {"Sefiller", other.title}


def test_public_payload_has_no_internal_fields(client, db):
    v = mk_venue(db)
    p = mk_production(db, "Oyun")
    mk_performance(db, p, v, internal_notes="GİZLİ NOT")
    raw = client.get(f"/api/v1/productions/{p.slug}").text + client.get("/api/v1/performances").text
    assert "GİZLİ NOT" not in raw
    assert "internal_notes" not in raw
