"""Theatre content: productions, credits, media, venues, performances, articles, organisation and legal texts."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin
from app.models._types import str_enum, uuid_pk


class PublicationStatus(enum.StrEnum):
    draft = "draft"
    published = "published"
    archived = "archived"


class PerformanceStatus(enum.StrEnum):
    scheduled = "scheduled"
    cancelled = "cancelled"


class Visibility(enum.StrEnum):
    draft = "draft"
    published = "published"


class CreditRole(enum.StrEnum):
    author = "author"
    director = "director"
    assistant_director = "assistant_director"
    translator = "translator"
    adaptation = "adaptation"
    poster_design = "poster_design"
    cast = "cast"
    other = "other"


CREDIT_ROLE_LABELS_TR = {
    CreditRole.author: "Yazar",
    CreditRole.director: "Yönetmen",
    CreditRole.assistant_director: "Yönetmen Yardımcısı",
    CreditRole.translator: "Çeviri",
    CreditRole.adaptation: "Uyarlama",
    CreditRole.poster_design: "Afiş Tasarım",
    CreditRole.cast: "Oyuncu",
    CreditRole.other: "Diğer",
}


class MediaAsset(TimestampMixin, Base):
    """A stored file. Records hold storage *keys*, never provider-specific URLs."""

    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = uuid_pk()
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    content_type: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    byte_size: Mapped[int] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    # {"sm": {"key": .., "width": .., "height": .., "content_type": ..}, "lg": {...}}
    variants: Mapped[dict] = mapped_column(JSONB, default=dict)
    alt_text: Mapped[str | None] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(16), default="upload")  # upload | import
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )


class Production(TimestampMixin, Base):
    __tablename__ = "productions"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes BETWEEN 1 AND 1440", name="duration_range"
        ),
        CheckConstraint("act_count IS NULL OR act_count BETWEEN 1 AND 20", name="act_range"),
        Index("ix_productions_status_featured", "status", "is_featured"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    short_description: Mapped[str | None] = mapped_column(String(400))
    description: Mapped[str | None] = mapped_column(Text)
    genres: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    act_count: Mapped[int | None] = mapped_column(Integer)
    # Original free-text duration as supplied (e.g. "2 Saat / 2 Perde"); kept for provenance.
    duration_text: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[PublicationStatus] = mapped_column(
        str_enum(PublicationStatus, "production_status"), default=PublicationStatus.draft, index=True
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    # "Sahnede" repertoire flag — editorial metadata, NOT proof of real-world availability.
    on_stage: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Position in the home screen's "Repertuvar" strip (1 = leftmost); NULL = not shown there. Separate
    # from sort_order so curating the home screen does not reshuffle the catalogue.
    home_order: Mapped[int | None] = mapped_column(Integer)
    poster_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="RESTRICT"))
    first_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    import_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))

    poster: Mapped[MediaAsset | None] = relationship(lazy="joined")
    credits: Mapped[list["ProductionCredit"]] = relationship(
        back_populates="production",
        cascade="all, delete-orphan",
        order_by="ProductionCredit.position",
        lazy="selectin",
    )
    images: Mapped[list["ProductionImage"]] = relationship(
        back_populates="production",
        cascade="all, delete-orphan",
        order_by="ProductionImage.position",
        lazy="selectin",
    )
    videos: Mapped[list["ProductionVideo"]] = relationship(
        back_populates="production",
        cascade="all, delete-orphan",
        order_by="ProductionVideo.position",
        lazy="selectin",
    )


class ProductionCredit(Base):
    __tablename__ = "production_credits"

    id: Mapped[uuid.UUID] = uuid_pk()
    production_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[CreditRole] = mapped_column(str_enum(CreditRole, "credit_role"))
    role_label: Mapped[str | None] = mapped_column(String(80))  # custom label, mainly for role=other
    name: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)

    production: Mapped[Production] = relationship(back_populates="credits")


class ProductionImage(Base):
    __tablename__ = "production_images"
    __table_args__ = (UniqueConstraint("production_id", "media_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    production_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    caption: Mapped[str | None] = mapped_column(String(300))

    production: Mapped[Production] = relationship(back_populates="images")
    media: Mapped[MediaAsset] = relationship(lazy="joined")


class ProductionVideo(Base):
    __tablename__ = "production_videos"

    id: Mapped[uuid.UUID] = uuid_pk()
    production_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)

    production: Mapped[Production] = relationship(back_populates="videos")


class Venue(TimestampMixin, Base):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(400))
    district: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    maps_url: Mapped[str | None] = mapped_column(String(500))
    public_info: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Istanbul")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    import_key: Mapped[str | None] = mapped_column(String(120), unique=True)


class Performance(TimestampMixin, Base):
    """A single dated showing. Independent of the production's publication status."""

    __tablename__ = "performances"
    __table_args__ = (
        Index("ix_performances_public", "visibility", "status", "starts_at"),
        Index("ix_performances_venue_start", "venue_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    production_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("productions.id", ondelete="RESTRICT"), index=True
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[PerformanceStatus] = mapped_column(
        str_enum(PerformanceStatus, "performance_status"), default=PerformanceStatus.scheduled
    )
    visibility: Mapped[Visibility] = mapped_column(
        str_enum(Visibility, "performance_visibility"), default=Visibility.draft
    )
    public_note: Mapped[str | None] = mapped_column(String(500))
    internal_notes: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_note: Mapped[str | None] = mapped_column(String(500))
    rescheduled_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rescheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reschedule_count: Mapped[int] = mapped_column(Integer, default=0)
    # Set the first time the performance became publicly visible. Only "announced" performances
    # trigger schedule-change notifications.
    first_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))

    production: Mapped[Production] = relationship(lazy="joined")
    venue: Mapped[Venue] = relationship(lazy="joined")


class Article(TimestampMixin, Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    image_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="RESTRICT"))
    status: Mapped[Visibility] = mapped_column(str_enum(Visibility, "article_status"), default=Visibility.draft)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))

    image: Mapped[MediaAsset | None] = relationship(lazy="joined")


class OrganizationProfile(Base):
    """Singleton row (id=1) with the organisation's public identity and About content."""

    __tablename__ = "organization_profile"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str | None] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(String(400))
    phones: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    email: Mapped[str | None] = mapped_column(String(200))
    website_url: Mapped[str | None] = mapped_column(String(300))
    instagram_url: Mapped[str | None] = mapped_column(String(300))
    x_url: Mapped[str | None] = mapped_column(String(300))
    youtube_url: Mapped[str | None] = mapped_column(String(300))
    # {"motto", "story_title", "story", "quote", "quote_author", "values": [{"title","text"}], "mission", "vision"}
    about: Mapped[dict] = mapped_column(JSONB, default=dict)
    logo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    logo: Mapped[MediaAsset | None] = relationship(lazy="joined")


class LegalDocument(TimestampMixin, Base):
    __tablename__ = "legal_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    # mobile_app | website | all — e.g. the cookie policy is website-only.
    applies_to: Mapped[str] = mapped_column(String(20), default="all")
    status: Mapped[Visibility] = mapped_column(str_enum(Visibility, "legal_status"), default=Visibility.draft)
    review_note: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    import_key: Mapped[str | None] = mapped_column(String(120), unique=True)


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_sha256: Mapped[str] = mapped_column(String(64))
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
