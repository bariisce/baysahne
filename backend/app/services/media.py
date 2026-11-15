import hashlib
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.text import utcnow
from app.models import AdminUser, Article, MediaAsset, OrganizationProfile, Production, ProductionImage
from app.storage import get_storage
from app.storage.images import ImageRejected, process_image


def store_image(
    db: Session,
    data: bytes,
    *,
    original_filename: str | None,
    source: str = "upload",
    uploaded_by: AdminUser | None = None,
    alt_text: str | None = None,
) -> tuple[MediaAsset, bool]:
    """Validate, re-encode and store an image. Returns (asset, created).

    Identical bytes (same SHA-256) reuse the existing asset, which makes imports idempotent and
    avoids duplicate uploads.
    """
    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(MediaAsset).where(MediaAsset.sha256 == digest))
    if existing:
        return existing, False
    try:
        processed = process_image(data)
    except ImageRejected as e:
        raise AppError(400, "invalid_image", str(e)) from e

    storage = get_storage()
    asset_id = uuid.uuid4()
    now = utcnow()
    prefix = f"images/{now:%Y}/{now:%m}/{asset_id}"
    key = f"{prefix}.{processed.original.ext}"
    written: list[str] = []
    try:
        storage.put(key, processed.original.data, processed.original.content_type)
        written.append(key)
        variants = {}
        for name, v in processed.variants.items():
            vkey = f"{prefix}_{name}.{v.ext}"
            storage.put(vkey, v.data, v.content_type)
            written.append(vkey)
            variants[name] = {"key": vkey, "width": v.width, "height": v.height, "content_type": v.content_type}
    except Exception:
        for k in written:
            storage.delete(k)
        raise

    safe_name = (original_filename or "")[-200:] or None
    asset = MediaAsset(
        id=asset_id,
        storage_key=key,
        content_type=processed.original.content_type,
        original_filename=safe_name,
        byte_size=len(processed.original.data),
        width=processed.original.width,
        height=processed.original.height,
        sha256=digest,
        variants=variants,
        alt_text=alt_text,
        source=source,
        uploaded_by_id=uploaded_by.id if uploaded_by else None,
    )
    db.add(asset)
    db.flush()
    return asset, True


def usage(db: Session, media_id: uuid.UUID) -> list[dict]:
    """Every place an asset is referenced. Deletion is refused while this is non-empty."""
    refs: list[dict] = []
    for p in db.scalars(select(Production).where(Production.poster_id == media_id)):
        refs.append({"type": "production_poster", "id": str(p.id), "label": p.title})
    rows = db.execute(
        select(Production.id, Production.title)
        .join(ProductionImage, ProductionImage.production_id == Production.id)
        .where(ProductionImage.media_id == media_id)
    )
    for pid, title in rows:
        refs.append({"type": "production_gallery", "id": str(pid), "label": title})
    for a in db.scalars(select(Article).where(Article.image_id == media_id)):
        refs.append({"type": "article_image", "id": str(a.id), "label": a.title})
    if db.scalar(select(func.count()).select_from(OrganizationProfile).where(OrganizationProfile.logo_id == media_id)):
        refs.append({"type": "organization_logo", "id": "1", "label": "Kurum logosu"})
    return refs


def delete_asset(db: Session, asset: MediaAsset) -> None:
    refs = usage(db, asset.id)
    if refs:
        raise AppError(
            409, "media_in_use", "Bu görsel hâlâ kullanılıyor; önce kullanıldığı yerlerden kaldırın.", {"usage": refs}
        )
    keys = [asset.storage_key] + [v["key"] for v in (asset.variants or {}).values()]
    db.delete(asset)
    db.flush()
    storage = get_storage()
    for k in keys:
        storage.delete(k)


def image_dict(asset: MediaAsset | None) -> dict | None:
    if asset is None:
        return None
    storage = get_storage()
    out = {
        "id": str(asset.id),
        "url": storage.url(asset.storage_key),
        "width": asset.width,
        "height": asset.height,
        "alt": asset.alt_text,
    }
    for name in ("sm", "lg"):
        v = (asset.variants or {}).get(name)
        out[name] = {"url": storage.url(v["key"]), "width": v["width"], "height": v["height"]} if v else None
    return out
