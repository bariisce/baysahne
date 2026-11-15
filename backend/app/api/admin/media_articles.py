import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, require_editor
from app.config import get_settings
from app.core.errors import AppError, conflict, not_found
from app.core.text import slugify, utcnow
from app.db import get_db
from app.models import AdminUser, Article, MediaAsset, Visibility
from app.schemas.common import OptText, PageNo, PageSize, ReqText, Slug, StrictModel
from app.services import audit, media, serialize

router = APIRouter(prefix="/api/v1/admin", tags=["admin-media"])

ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp"}


def media_admin(db: Session, m: MediaAsset, with_usage: bool = False) -> dict:
    out = {
        **media.image_dict(m),
        "original_filename": m.original_filename,
        "content_type": m.content_type,
        "byte_size": m.byte_size,
        "source": m.source,
        "created_at": m.created_at.isoformat(),
    }
    if with_usage:
        out["usage"] = media.usage(db, m.id)
    return out


@router.post("/media", status_code=201)
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_editor),
):
    limit = get_settings().media_max_upload_mb * 1024 * 1024
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise AppError(415, "unsupported_type", "Yalnızca JPEG, PNG veya WebP görselleri yüklenebilir.")
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise AppError(413, "file_too_large", f"Dosya en fazla {get_settings().media_max_upload_mb} MB olabilir.")
    if not data:
        raise AppError(400, "empty_file", "Dosya boş.")
    asset, created = media.store_image(db, data, original_filename=file.filename, uploaded_by=user)
    if created:
        audit.record(db, user, "media.upload", entity_type="media", entity_id=asset.id,
                     summary=f"Görsel yüklendi: {file.filename}", ip=client_ip(request))
    db.commit()
    return {**media_admin(db, asset), "duplicate": not created}


@router.get("/media")
def list_media(page: PageNo = 1, page_size: PageSize = 48, db: Session = Depends(get_db),
               _: AdminUser = Depends(require_editor)):
    total = db.scalar(select(func.count()).select_from(MediaAsset))
    rows = db.scalars(
        select(MediaAsset).order_by(MediaAsset.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [media_admin(db, m) for m in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/media/{media_id}")
def get_media(media_id: uuid.UUID, db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    m = db.get(MediaAsset, media_id)
    if not m:
        raise not_found("Görsel bulunamadı.")
    return media_admin(db, m, with_usage=True)


class MediaPatch(StrictModel):
    alt_text: OptText = Field(default=None, max_length=300)


@router.patch("/media/{media_id}")
def update_media(media_id: uuid.UUID, body: MediaPatch, db: Session = Depends(get_db),
                 _: AdminUser = Depends(require_editor)):
    m = db.get(MediaAsset, media_id)
    if not m:
        raise not_found("Görsel bulunamadı.")
    m.alt_text = body.alt_text
    db.commit()
    return media_admin(db, m, with_usage=True)


@router.delete("/media/{media_id}", status_code=204)
def delete_media(media_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                 user: AdminUser = Depends(require_editor)):
    m = db.get(MediaAsset, media_id)
    if not m:
        raise not_found("Görsel bulunamadı.")
    name = m.original_filename
    media.delete_asset(db, m)  # raises 409 media_in_use while referenced
    audit.record(db, user, "media.delete", entity_type="media", entity_id=media_id,
                 summary=f"Görsel silindi: {name}", ip=client_ip(request))
    db.commit()


# ---------------------------------------------------------------- articles


class ArticleIn(StrictModel):
    title: ReqText = Field(max_length=200)
    slug: Slug = None
    body: ReqText = Field(max_length=50000)
    image_id: uuid.UUID | None = None


class ArticlePublishIn(StrictModel):
    published_at: str | None = Field(
        default=None, description="Optional ISO datetime; a future value schedules publication", max_length=40)


def article_admin(a: Article) -> dict:
    return {
        **serialize.article_public(a, full=True),
        "status": a.status.value,
        "image_id": str(a.image_id) if a.image_id else None,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
    }


def _article(db: Session, aid: uuid.UUID) -> Article:
    a = db.get(Article, aid)
    if not a:
        raise not_found("Duyuru bulunamadı.")
    return a


def _slug_for(db: Session, wanted: str | None, title: str, exclude=None) -> str:
    if wanted:
        if db.scalar(select(Article.id).where(Article.slug == wanted, Article.id != exclude)):
            raise conflict("slug_taken", "Bu kısa ad başka bir duyuruda kullanılıyor.")
        return wanted
    base, n = slugify(title), 2
    slug = base
    while db.scalar(select(Article.id).where(Article.slug == slug, Article.id != exclude)):
        slug, n = f"{base}-{n}", n + 1
    return slug


@router.get("/articles", tags=["admin-articles"])
def list_articles(db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    rows = db.scalars(select(Article).order_by(Article.created_at.desc())).unique().all()
    return {"items": [article_admin(a) for a in rows]}


@router.post("/articles", status_code=201, tags=["admin-articles"])
def create_article(body: ArticleIn, request: Request, db: Session = Depends(get_db),
                   user: AdminUser = Depends(require_editor)):
    if body.image_id and not db.get(MediaAsset, body.image_id):
        raise not_found("Görsel bulunamadı.")
    a = Article(title=body.title, body=body.body, image_id=body.image_id, slug=_slug_for(db, body.slug, body.title),
                status=Visibility.draft, updated_by_id=user.id)
    db.add(a)
    db.flush()
    audit.record(db, user, "article.create", entity_type="article", entity_id=a.id,
                 summary=f"Duyuru oluşturuldu: {a.title}", ip=client_ip(request))
    db.commit()
    db.refresh(a)
    return article_admin(a)


@router.get("/articles/{article_id}", tags=["admin-articles"])
def get_article(article_id: uuid.UUID, db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    return article_admin(_article(db, article_id))


@router.put("/articles/{article_id}", tags=["admin-articles"])
def update_article(article_id: uuid.UUID, body: ArticleIn, request: Request, db: Session = Depends(get_db),
                   user: AdminUser = Depends(require_editor)):
    a = _article(db, article_id)
    if body.image_id and not db.get(MediaAsset, body.image_id):
        raise not_found("Görsel bulunamadı.")
    a.title, a.body, a.image_id = body.title, body.body, body.image_id
    a.slug = _slug_for(db, body.slug or a.slug, body.title, exclude=a.id)
    a.updated_by_id = user.id
    audit.record(db, user, "article.update", entity_type="article", entity_id=a.id,
                 summary=f"Duyuru güncellendi: {a.title}", ip=client_ip(request))
    db.commit()
    db.refresh(a)
    return article_admin(a)


@router.post("/articles/{article_id}/publish", tags=["admin-articles"])
def publish_article(article_id: uuid.UUID, body: ArticlePublishIn, request: Request, db: Session = Depends(get_db),
                    user: AdminUser = Depends(require_editor)):
    from datetime import datetime

    a = _article(db, article_id)
    when = utcnow()
    if body.published_at:
        try:
            when = datetime.fromisoformat(body.published_at)
        except ValueError as e:
            raise AppError(422, "validation_error", "Geçerli bir yayın tarihi girin.") from e
        if when.tzinfo is None:
            raise AppError(422, "validation_error", "Yayın tarihi saat dilimi içermelidir.")
    a.status = Visibility.published
    a.published_at = when
    audit.record(db, user, "article.publish", entity_type="article", entity_id=a.id,
                 summary=f"Duyuru yayınlandı: {a.title}", ip=client_ip(request))
    db.commit()
    return article_admin(a)


@router.post("/articles/{article_id}/unpublish", tags=["admin-articles"])
def unpublish_article(article_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                      user: AdminUser = Depends(require_editor)):
    a = _article(db, article_id)
    a.status = Visibility.draft
    audit.record(db, user, "article.unpublish", entity_type="article", entity_id=a.id,
                 summary=f"Duyuru yayından kaldırıldı: {a.title}", ip=client_ip(request))
    db.commit()
    return article_admin(a)


@router.delete("/articles/{article_id}", status_code=204, tags=["admin-articles"])
def delete_article(article_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                   user: AdminUser = Depends(require_editor)):
    a = _article(db, article_id)
    audit.record(db, user, "article.delete", entity_type="article", entity_id=a.id,
                 summary=f"Duyuru silindi: {a.title}", ip=client_ip(request))
    db.delete(a)
    db.commit()
