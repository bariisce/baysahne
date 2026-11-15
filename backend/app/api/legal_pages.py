"""Server-rendered public legal pages (e.g. the privacy-policy URL required by App Store / Google Play).

Only *published* documents are shown. Content is HTML-escaped; paragraphs come from blank lines.
"""

import html

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LegalDocument, OrganizationProfile, Visibility

router = APIRouter(tags=["legal-pages"], include_in_schema=False)

_PAGE = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>
:root{{color-scheme:dark;--bg:#0C0A09;--fg:#F5F0E8;--muted:#9C8B72;--gold:#C4973F}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 Inter,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:720px;margin:0 auto;padding:40px 20px 80px}}
h1{{font-family:"Playfair Display",Georgia,serif;font-weight:600;font-size:32px;margin:0 0 8px}}
.meta{{color:var(--muted);font-size:14px;margin-bottom:32px}} a{{color:var(--gold)}}
p{{margin:0 0 16px;white-space:pre-line}} li{{margin:6px 0}}
</style></head><body><main>{content}</main></body></html>"""


def _paragraphs(text: str) -> str:
    return "".join(f"<p>{html.escape(block.strip())}</p>" for block in text.split("\n\n") if block.strip())


@router.get("/legal", response_class=HTMLResponse)
def legal_index(db: Session = Depends(get_db)):
    docs = db.scalars(select(LegalDocument).where(LegalDocument.status == Visibility.published)
                      .order_by(LegalDocument.title)).all()
    org = db.get(OrganizationProfile, 1)
    name = html.escape(org.name if org else "Bay Sahne")
    items = "".join(f'<li><a href="/legal/{html.escape(d.slug)}">{html.escape(d.title)}</a></li>' for d in docs)
    body = items and f"<ul>{items}</ul>" or "<p>Henüz yayınlanmış bir yasal metin bulunmuyor.</p>"
    content = f"<h1>Yasal metinler</h1><div class=meta>{name}</div>{body}"
    return _PAGE.format(title=f"{name} — Yasal metinler", content=content)


@router.get("/legal/{slug}", response_class=HTMLResponse)
def legal_page(slug: str, db: Session = Depends(get_db)):
    d = db.scalar(select(LegalDocument).where(LegalDocument.slug == slug, LegalDocument.status == Visibility.published))
    if not d:
        return HTMLResponse(_PAGE.format(title="Bulunamadı", content="<h1>Belge bulunamadı</h1>"), status_code=404)
    updated = (d.published_at or d.updated_at).strftime("%d.%m.%Y")
    content = (f"<h1>{html.escape(d.title)}</h1><div class=meta>Son güncelleme: {updated}</div>"
               f"{_paragraphs(d.body)}")
    return _PAGE.format(title=html.escape(d.title), content=content)
