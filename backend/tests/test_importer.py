from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import REPO_ROOT
from app.importer.run import DOCX_NAME, import_content, write_report
from app.models import (
    LegalDocument,
    MediaAsset,
    NotificationJob,
    OrganizationProfile,
    Performance,
    Production,
    ProductionImage,
    Visibility,
)

SOURCE = REPO_ROOT
pytestmark = pytest.mark.skipif(not (SOURCE / DOCX_NAME).is_file(), reason="source document not present")


def counts(db):
    return {m.__name__: db.scalar(select(func.count()).select_from(m))
            for m in (Production, MediaAsset, ProductionImage, LegalDocument, Performance, NotificationJob)}


def test_import_is_complete_and_idempotent(db, client, tmp_path: Path):
    rep = import_content(db, SOURCE)
    db.commit()
    first = counts(db)
    assert first["Production"] == 11
    assert first["ProductionImage"] == 79
    assert first["Performance"] == 0 and first["NotificationJob"] == 0  # nothing invented, nothing sent
    assert first["LegalDocument"] == 4
    assert {f["file"] for f in rep.missing_assets} == {f"r&jpic{i}.svg" for i in range(2, 12)}

    rep2 = import_content(db, SOURCE)
    db.commit()
    assert counts(db) == first
    assert rep2.created == [] and rep2.media_created == 0
    assert [p["result"] for p in rep2.productions] == ["already present"] * 11

    # every legal text is a draft; none is public
    assert all(d.status == Visibility.draft for d in db.scalars(select(LegalDocument)))
    assert client.get("/api/v1/legal").json()["items"] == []

    lys = client.get("/api/v1/productions/lysistrata").json()
    assert lys["on_stage"] is True and lys["duration_label"] == "85 dakika"
    assert [c["name"] for c in lys["credits"] if c["role"] == "director"] == ["S. Çağrı Pepesöyler"]
    fr = client.get("/api/v1/productions/frankenstein").json()
    assert fr["duration_label"] == "2 perde" and fr["gallery"] == []
    assert {c["label"] for c in fr["credits"]} == {"Yazar", "Yönetmen", "Afiş Tasarım", "Çeviri"}
    assert fr["poster"]["sm"]["url"].endswith("_sm.webp")
    antigone = client.get("/api/v1/productions/antigone").json()
    assert antigone["description"] is None and antigone["excerpt"] is None
    bygr = client.get("/api/v1/productions/bir-yaz-gecesi-ruyasi").json()
    assert bygr["videos"][0]["youtube_id"] == "a46Go3Q6X7k"

    org = db.get(OrganizationProfile, 1)
    assert org.email == "baysahne@gmail.com" and org.x_url == "https://x.com/baysahne"
    assert org.phones == ["+90 505 129 50 00", "+90 536 853 16 26"]
    assert org.about["motto"] == "Sahnede Gerçek, Kuliste Aile."
    assert [v["title"] for v in org.about["values"]] == ["Tutku", "Kolektif Ruh", "Yenilik"]
    assert org.about["quote_author"] == "S. Çağrı Pepesöyler"
    assert org.logo_id is not None

    out = tmp_path / "report.md"
    write_report(rep, out)
    text = out.read_text(encoding="utf-8")
    assert "r&jpic2.svg" in text and "lysistratabaysahne.svg` → WEBP" in text
