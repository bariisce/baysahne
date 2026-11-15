"""Parser for `BAY SAHNE BİLGİLER.docx`.

Reads the .docx (a ZIP of WordprocessingML) with the standard library, so no extra dependency.
It yields a structured, *unmodified* representation. Every normalisation is applied separately and
recorded as a `Transform`, so the import report can list exactly what changed and why.
"""

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

FIELD_RE = re.compile(r"^(?P<key>[A-Za-zÇĞİÖŞÜçğıöşü \-]{1,40}):\s*(?P<value>.*)$", re.S)
KUNYE = {"kunye", "künye"}
SECTION_ON_STAGE = "SAHNEDEKİ OYUNLAR"
ABOUT_HEADING = "HAKKIMIZDA"
LEGAL_HEADINGS = {
    "GİZLİLİK POLİTİKASI": ("gizlilik-politikasi-web", "Gizlilik Politikası (web sitesi metni)", "website"),
    "KULLANIM ŞARTLARI": ("kullanim-sartlari-web", "Kullanım Şartları (web sitesi metni)", "website"),
    "ÇEREZ POLİTİKASI": ("cerez-politikasi-web", "Çerez Politikası (web sitesi)", "website"),
    "KVKK AYDINLATMA METNİ": ("kvkk-aydinlatma-web", "KVKK Aydınlatma Metni (web sitesi metni)", "website"),
}


@dataclass
class Paragraph:
    text: str
    style: str | None
    links: list[str]


@dataclass
class Transform:
    where: str
    before: str
    after: str
    reason: str


@dataclass
class SourceProduction:
    title: str
    order: int
    on_stage_section: bool
    story: str | None = None
    fields: dict[str, str] = field(default_factory=dict)  # raw "Key: value" pairs in document order
    poster_ref: str | None = None
    gallery_refs: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)


@dataclass
class SourceDocument:
    sha256: str
    organization: dict
    productions: list[SourceProduction]
    about_paragraphs: list[Paragraph]
    legal: dict[str, list[Paragraph]]
    paragraphs: list[Paragraph]


def read_paragraphs(path: Path) -> list[Paragraph]:
    with zipfile.ZipFile(path) as z:
        # Operator-supplied file; stdlib expat (>= 2.4) caps entity amplification and never fetches external entities.
        doc = ET.fromstring(z.read("word/document.xml"))  # noqa: S314
        rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))  # noqa: S314
    targets = {r.get("Id"): r.get("Target") for r in rels}
    out = []
    for p in doc.iter(f"{W}p"):
        style_el = p.find(f"{W}pPr/{W}pStyle")
        parts, links = [], []
        for el in p.iter():
            if el.tag == f"{W}t":
                parts.append(el.text or "")
            elif el.tag in (f"{W}br", f"{W}cr"):
                parts.append("\n")
            elif el.tag == f"{W}tab":
                parts.append("\t")
            elif el.tag == f"{W}hyperlink" and el.get(f"{R}id") in targets:
                links.append(targets[el.get(f"{R}id")])
        out.append(Paragraph("".join(parts), style_el.get(f"{W}val") if style_el is not None else None, links))
    return out


def _split_refs(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def parse(path: Path) -> SourceDocument:
    import hashlib

    paras = read_paragraphs(path)
    texts = [p.text.strip() for p in paras]

    # --- organisation block (before "OYUN BİLGİLERİ:")
    org: dict = {}
    i = 0
    while i < len(texts) and not texts[i].upper().startswith("OYUN BİLGİLERİ"):
        m = FIELD_RE.match(texts[i])
        if m:
            org[m.group("key").strip().lower()] = m.group("value").strip()
        i += 1
    i += 1

    # --- productions (until "HAKKIMIZDA")
    productions: list[SourceProduction] = []
    on_stage = False
    current: SourceProduction | None = None
    expecting_story = False
    while i < len(texts) and texts[i] != ABOUT_HEADING:
        t = texts[i]
        i += 1
        if not t:
            continue
        if t == SECTION_ON_STAGE:
            on_stage = True
            continue
        if expecting_story and current and not FIELD_RE.match(t) and t.lower() not in KUNYE:
            current.story = t
            expecting_story = False
            continue
        # A title paragraph may carry the story in the same paragraph ("FrankensteinHikaye: ...").
        story_inline = re.match(r"^(?P<title>[^:\n]+?)\s*Hikaye:\s*(?P<story>.*)$", t, re.S)
        if t.lower() in KUNYE:
            continue
        m = FIELD_RE.match(t)
        if story_inline and not t.startswith("Hikaye:"):
            current = SourceProduction(title=story_inline.group("title").strip(), order=len(productions),
                                       on_stage_section=on_stage)
            productions.append(current)
            current.story = story_inline.group("story").strip() or None
            continue
        if m and current is not None:
            key, value = m.group("key").strip(), m.group("value").strip()
            low = key.lower()
            if low == "hikaye":
                current.story = value or None
                expecting_story = not value
            elif low == "afiş":
                current.poster_ref = _split_refs(value)[0] if _split_refs(value) else None
            elif low == "oyundan kareler":
                current.gallery_refs = _split_refs(value)
            elif low == "oyun video linki":
                current.video_urls = paras[i - 1].links or [value]
            elif low == "görseller":
                pass
            else:
                current.fields[key] = value
            continue
        if not m and ":" not in t:
            # A bare line outside a künye block starts a new production.
            current = SourceProduction(title=t, order=len(productions), on_stage_section=on_stage)
            productions.append(current)
            expecting_story = False
            continue

    # --- about (until first legal heading) and legal sections
    about: list[Paragraph] = []
    legal: dict[str, list[Paragraph]] = {}
    section = "about"
    while i < len(paras):
        t = texts[i]
        if t in LEGAL_HEADINGS:
            section = t
            legal[t] = []
        elif section == "about":
            if t and t != ABOUT_HEADING:
                about.append(paras[i])
        else:
            legal[section].append(paras[i])
        i += 1

    return SourceDocument(
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        organization=org,
        productions=productions,
        about_paragraphs=about,
        legal=legal,
        paragraphs=paras,
    )


# ---------------------------------------------------------------- normalisation helpers (recorded)


def join_visual_breaks(text: str, where: str, log: list[Transform]) -> str:
    """Headings and the motto use manual line breaks for layout ("Sahnede Gerçek,⏎Kuliste Aile.").
    In the app they are rendered on one line, so a break becomes a space. Recorded in the report."""
    joined = " ".join(part.strip() for part in text.split("\n") if part.strip())
    if joined != text:
        log.append(Transform(where, text.replace("\n", "⏎"), joined, "Layout line break joined with a space"))
    return joined


def normalize_initial_spacing(name: str, where: str, log: list[Transform]) -> str:
    """'S.Çağrı Pepesöyler' → 'S. Çağrı Pepesöyler' so one person is spelled one way across credits."""
    fixed = re.sub(r"\b([A-ZÇĞİÖŞÜ])\.(?=[A-ZÇĞİÖŞÜ][a-zçğıöşü])", r"\1. ", name)
    if fixed != name:
        log.append(Transform(where, name, fixed,
                             "Missing space after initial added (consistent with the other credits)"))
    return fixed


def parse_duration(text: str | None) -> tuple[int | None, int | None]:
    """'120 Dakika / 2 Perde' → (120, 2); '2 Saat / 2 Perde' → (120, 2); '2 Perde' → (None, 2)."""
    if not text:
        return None, None
    minutes = acts = None
    if m := re.search(r"(\d+)\s*Dakika", text, re.I):
        minutes = int(m.group(1))
    elif m := re.search(r"(\d+)\s*Saat", text, re.I):
        minutes = int(m.group(1)) * 60
    if m := re.search(r"(\d+)\s*Perde", text, re.I):
        acts = int(m.group(1))
    return minutes, acts
