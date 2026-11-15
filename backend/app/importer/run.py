"""Idempotent initial-content import from `content/BAY SAHNE BİLGİLER.docx` + the images under `content/media`.

Re-running is safe:
- productions, venue, legal texts and the organisation profile are keyed by stable `import_key`s and are
  only CREATED when missing. Records that already exist are left untouched, so staff edits made in the
  admin panel are never overwritten by a later import.
- media is de-duplicated by SHA-256 of the file bytes.
- the importer never creates notification jobs.

Content decisions (see docs/CONTENT_IMPORT_REPORT.md):
- Imported productions are `published` (this is the theatre's official repertoire, already public on
  baysahne.com). `on_stage` mirrors the "SAHNEDEKİ OYUNLAR" section as editable metadata only.
- No performance dates, cast, venues per play, prices or age ratings are created: the source has none.
"""

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import REPO_ROOT
from app.core.text import slugify, utcnow
from app.db import SessionLocal
from app.importer import docx_source as src
from app.importer.report import write_report
from app.models import (
    CREDIT_ROLE_LABELS_TR as CREDIT_LABELS,
)
from app.models import (
    CreditRole,
    ImportRun,
    LegalDocument,
    OrganizationProfile,
    Production,
    ProductionCredit,
    ProductionImage,
    ProductionVideo,
    PublicationStatus,
    Venue,
    Visibility,
)
from app.services.media import store_image

# The supplied source material: the document at the top, images anywhere below it (content/media/<production>/).
CONTENT_DIR = REPO_ROOT / "content"
DOCX_NAME = "BAY SAHNE BİLGİLER.docx"
ORG_LOGO_FILE = "baysahnelogo1.svg"  # current wordmark; identical asset is served as the logo on baysahne.com

CREDIT_KEYS = {
    "yazar": CreditRole.author,
    "yönetmen": CreditRole.director,
    "yönetmen yardımcısı": CreditRole.assistant_director,
    "çeviri": CreditRole.translator,
    "afiş tasarım": CreditRole.poster_design,
}
DESCRIPTIVE_KEYS = {"tür", "süre"}

LEGAL_REVIEW_NOTE = (
    "Web sitesi için yazılmış kaynak metin olduğu gibi içe aktarıldı. Mobil uygulamayı doğru tanımlamıyor "
    "(üyelik, yorum sistemi, Firebase Authentication/Firestore gibi uygulamada olmayan işlemlerden söz ediyor). "
    "Yayınlamadan önce kurum ve gerekirse bir hukuk uzmanı tarafından gözden geçirilmelidir. "
    "Bkz. docs/LEGAL_REVIEW.md."
)

KNOWN_SOURCE_NOTES = [
    ("Frankenstein", "Author is written 'Mary Shelly' while the description says 'Mary Shelley'. Kept as in the "
                     "source; the organisation should confirm."),
    ("Frankenstein", "Poster file is named 'frankesteinbaysahne.svg' (differs from the title's spelling). Found "
                     "under that name; no problem."),
    ("Hayvan Çiftliği", "Description contains 'bie çiftlikte', probably a typo for 'bir çiftlikte'. Kept as in "
                        "the source."),
    ("Kibarlık Budalası", "Author is written 'Moliere' (original spelling: Molière). Kept as in the source."),
]


@dataclass
class Report:
    started_at: str
    source_sha256: str = ""
    created: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    media_created: int = 0
    media_reused: int = 0
    media_by_type: dict[str, int] = field(default_factory=dict)
    extension_mismatch: list[tuple[str, str]] = field(default_factory=list)
    missing_assets: list[dict] = field(default_factory=list)
    renamed_assets: list[tuple[str, str]] = field(default_factory=list)
    unreferenced_assets: list[str] = field(default_factory=list)
    incomplete: list[dict] = field(default_factory=list)
    transforms: list[dict] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)
    productions: list[dict] = field(default_factory=list)


def _sniff(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    if data.lstrip()[:5] in (b"<?xml", b"<svg "):
        return "SVG"
    return "UNKNOWN"


# The supplied files are named `.svg` but are rasters; someone fixing a name keeps the stem and uses the real extension.
RENAMED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
IMAGE_EXTENSIONS = {".svg", *RENAMED_EXTENSIONS}


def media_index(folder: Path) -> dict[str, Path]:
    """Every image under the source folder, keyed by file name.

    The document refers to images by bare file name, so sub-folders (one per production, see content/media)
    only organise the files and may be rearranged freely. For the same reason a name must be unique.
    """
    index: dict[str, Path] = {}
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() not in IMAGE_EXTENSIONS or not path.is_file():
            continue
        if path.name in index:
            raise ValueError(
                f"Two source images are named '{path.name}': {index[path.name].relative_to(folder)} and "
                f"{path.relative_to(folder)}. The document refers to images by name; rename or remove one."
            )
        index[path.name] = path
    return index


def find_asset(index: dict[str, Path], name: str) -> Path | None:
    """The file the document refers to: the exact name, else the same name with a real image extension."""
    if name in index:
        return index[name]
    stem = Path(name).stem
    for ext in RENAMED_EXTENSIONS:
        for candidate in (f"{stem}{ext}", f"{stem}{ext.upper()}"):
            if candidate in index:
                return index[candidate]
    return None


def resolve_asset(folder: Path, name: str) -> Path | None:
    return find_asset(media_index(folder), name)


def _load_media(db: Session, index: dict[str, Path], name: str, rep: Report, where: str, used: set[str]):
    path = find_asset(index, name)
    if path is None:
        rep.missing_assets.append({"production": where, "file": name})
        return None
    if path.name != name:
        rep.renamed_assets.append((name, path.name))
    used.add(path.name)
    data = path.read_bytes()
    kind = _sniff(data)
    rep.media_by_type[kind] = rep.media_by_type.get(kind, 0) + 1
    if path.suffix.lower() == ".svg" and kind != "SVG":
        rep.extension_mismatch.append((name, kind))
    asset, created = store_image(db, data, original_filename=path.name, source="import")
    if created:
        rep.media_created += 1
    else:
        rep.media_reused += 1
    return asset


def import_content(db: Session, folder: Path) -> Report:
    rep = Report(started_at=utcnow().isoformat())
    doc = src.parse(folder / DOCX_NAME)
    media = media_index(folder)
    rep.source_sha256 = doc.sha256
    tlog: list[src.Transform] = []
    used_files: set[str] = set()
    now = utcnow()

    # ---- venue (the organisation's own address; staff can edit or add venues)
    org_fields = doc.organization
    address = org_fields.get("adres")
    venue_key = "docx:venue:primary"
    if not db.scalar(select(Venue).where(Venue.import_key == venue_key)):
        db.add(Venue(name=org_fields.get("unvan", "Bay Sahne"), address=address, district="Çukurova", city="Adana",
                     timezone="Europe/Istanbul", import_key=venue_key))
        rep.created.append("Venue: " + org_fields.get("unvan", "Bay Sahne"))
    else:
        rep.skipped_existing.append("Venue")

    # ---- productions: analyse the source fully (for the report), write only when missing
    for sp in doc.productions:
        key = f"docx:production:{slugify(sp.title)}"
        title = sp.title
        exists = db.scalar(select(Production.id).where(Production.import_key == key)) is not None
        fields = {k.lower(): v for k, v in sp.fields.items()}
        genres = [g.strip() for g in fields.get("tür", "").split(",") if g.strip()]
        duration_text = fields.get("süre") or None
        minutes, acts = src.parse_duration(duration_text)
        if duration_text and (minutes or acts):
            tlog.append(src.Transform(f"{title} / Süre", duration_text, f"dakika={minutes}, perde={acts}",
                                      "Free-text duration parsed into numeric fields; original text kept"))
        credits = []
        for raw_key, value in sp.fields.items():
            low = raw_key.lower()
            if low in DESCRIPTIVE_KEYS or not value:
                continue
            role = CREDIT_KEYS.get(low)
            name = src.normalize_initial_spacing(value, f"{title} / {raw_key}", tlog)
            credits.append((role or CreditRole.other, None if role else raw_key, name))
            if not role:
                rep.notes.append({"production": title,
                                  "note": f"Unknown credit field '{raw_key}' imported as role 'other'."})

        missing = []
        if not sp.story:
            missing.append("description (Hikaye)")
        if not duration_text:
            missing.append("duration")
        if not sp.gallery_refs:
            missing.append("production photos")
        if not sp.poster_ref:
            missing.append("poster")
        missing += ["cast list (not in source)", "performance dates (not in source)"]
        rep.incomplete.append({"production": title, "missing": missing})

        poster = None
        gallery = []
        if sp.poster_ref:
            poster = _load_media(db, media, sp.poster_ref, rep, title, used_files)
        for ref in sp.gallery_refs:
            asset = _load_media(db, media, ref, rep, title, used_files)
            if asset and asset.id not in {a.id for a in gallery}:
                gallery.append(asset)

        rep.productions.append({
            "title": title, "on_stage": sp.on_stage_section,
            "result": "already present" if exists else "created",
            "credits": [f"{label or CREDIT_LABELS[role]}: {name}" for role, label, name in credits],
            "genres": genres, "duration_text": duration_text, "poster": sp.poster_ref,
            "gallery_in_source": len(sp.gallery_refs), "gallery_imported": len(gallery), "videos": sp.video_urls,
        })
        if exists:
            rep.skipped_existing.append(f"Production: {title}")
            continue

        p = Production(
            title=title, slug=slugify(title), description=sp.story, genres=genres, duration_minutes=minutes,
            act_count=acts, duration_text=duration_text, status=PublicationStatus.published,
            on_stage=sp.on_stage_section, sort_order=sp.order * 10, first_published_at=now, published_at=now,
            import_key=key, poster_id=poster.id if poster else None,
        )
        p.credits = [ProductionCredit(role=r, role_label=lbl, name=n, position=i)
                     for i, (r, lbl, n) in enumerate(credits)]
        p.videos = [ProductionVideo(url=u, title="Oyun videosu", position=i) for i, u in enumerate(sp.video_urls)]
        p.images = [ProductionImage(media_id=a.id, position=i) for i, a in enumerate(gallery)]
        db.add(p)
        db.flush()
        rep.created.append(f"Production: {title}")

    # ---- organisation profile + about
    if not db.get(OrganizationProfile, 1):
        about = _about(doc.about_paragraphs, tlog)
        phones = [x.strip() for x in org_fields.get("telefon", "").split(",") if x.strip()]
        logo = _load_media(db, media, ORG_LOGO_FILE, rep, "Kurum logosu", used_files)
        db.add(OrganizationProfile(
            id=1, name=org_fields.get("unvan", "Bay Sahne"), short_name="Bay Sahne", address=address,
            phones=phones, email=org_fields.get("e-posta"), website_url=org_fields.get("web"),
            instagram_url=org_fields.get("instagram"), x_url=org_fields.get("x"),
            youtube_url=org_fields.get("youtube"), about=about, logo_id=logo.id if logo else None,
            updated_at=now))
        rep.created.append("Organisation profile and About content")
    else:
        rep.skipped_existing.append("Organisation profile")

    # ---- legal documents: imported verbatim as DRAFTS, never auto-published
    for heading, paras in doc.legal.items():
        slug, title, applies = src.LEGAL_HEADINGS[heading]
        key = f"docx:legal:{slug}"
        if db.scalar(select(LegalDocument).where(LegalDocument.import_key == key)):
            rep.skipped_existing.append(f"Legal text: {title}")
            continue
        body = "\n\n".join(p.text.strip() for p in paras if p.text.strip())
        db.add(LegalDocument(slug=slug, title=title, body=body, applies_to=applies, status=Visibility.draft,
                             review_note=LEGAL_REVIEW_NOTE, import_key=key))
        rep.created.append(f"Legal text (draft): {title}")

    # ---- supplied images the document never mentions
    rep.unreferenced_assets += sorted(name for name in media if name not in used_files)

    rep.transforms = [asdict(t) for t in tlog]
    rep.notes += [{"production": t, "note": n} for t, n in KNOWN_SOURCE_NOTES]
    db.add(ImportRun(started_at=utcnow(), finished_at=utcnow(), source_sha256=doc.sha256,
                     summary=json.loads(json.dumps(asdict(rep), default=str))))
    return rep


def _about(paras: list[src.Paragraph], tlog: list[src.Transform]) -> dict:
    """Map the HAKKIMIZDA block onto structured About fields using its own headings as anchors."""
    texts = [p.text.strip() for p in paras if p.text.strip()]

    def after(label: str, offset: int = 1) -> str | None:
        for i, t in enumerate(texts):
            if src.join_visual_breaks(t, "", []) == label and i + offset < len(texts):
                return texts[i + offset]
        return None

    about: dict = {}
    if len(texts) > 1:
        about["motto"] = src.join_visual_breaks(texts[1], "Hakkımızda / slogan", tlog)
    story_title = after("01. Kökler")
    if story_title:
        about["story_title"] = src.join_visual_breaks(story_title, "Hakkımızda / başlık", tlog)
        about["story"] = after("01. Kökler", 2)
    quote_i = next((i for i, t in enumerate(texts) if t.startswith("— ")), None)
    if quote_i:
        about["quote"] = texts[quote_i - 1]
        about["quote_author"] = texts[quote_i].removeprefix("— ").strip()
    values = []
    for name in ("Tutku", "Kolektif Ruh", "Yenilik"):
        if text := after(name):
            values.append({"title": name, "text": text})
    about["values"] = values
    about["mission"] = after("03. Misyon", 2)
    about["vision"] = after("04. Vizyon", 2)
    return {k: v for k, v in about.items() if v}


def main(source: str | None, report: str | None) -> int:
    folder = Path(source) if source else CONTENT_DIR
    if not (folder / DOCX_NAME).is_file():
        print(f"Source document not found: {folder / DOCX_NAME}", file=sys.stderr)
        return 1
    db = SessionLocal()
    try:
        rep = import_content(db, folder)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    out = Path(report) if report else REPO_ROOT / "docs" / "CONTENT_IMPORT_REPORT.md"
    write_report(rep, out)
    print(f"Import finished: {len(rep.created)} created, {len(rep.skipped_existing)} skipped, "
          f"{rep.media_created} new media, {rep.media_reused} reused, {len(rep.missing_assets)} missing assets.")
    print(f"Report written to {out}")
    return 0
