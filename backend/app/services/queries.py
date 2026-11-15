"""Public visibility rules live here, in one place, and are enforced server-side.

- A production is public only when status == published (drafts and archived are hidden).
- A performance is public only when its own visibility == published AND its production is public.
- Upcoming = starts_at > now. Cancelled upcoming performances stay visible but flagged, so audiences
  see the cancellation rather than silently losing the date. They never count as "available".
"""

import unicodedata
from datetime import datetime

from sqlalchemy import Select, any_, func, select
from sqlalchemy.orm import Session

from app.core.text import utcnow
from app.models import Performance, PerformanceStatus, Production, PublicationStatus, Visibility


def fold(text: str) -> str:
    """Turkish-aware, accent-insensitive fold for search ("MÜFETTİŞ" ~ "mufettis")."""
    text = text.replace("İ", "i").replace("I", "ı").lower()
    text = text.translate(str.maketrans("çğıöşü", "cgiosu"))
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def public_productions() -> Select:
    return select(Production).where(Production.status == PublicationStatus.published)


def public_performances(now: datetime | None = None, include_cancelled: bool = True) -> Select:
    now = now or utcnow()
    q = (
        select(Performance)
        .join(Production, Production.id == Performance.production_id)
        .where(
            Performance.visibility == Visibility.published,
            Production.status == PublicationStatus.published,
            Performance.starts_at > now,
        )
        .order_by(Performance.starts_at, Performance.id)
    )
    if not include_cancelled:
        q = q.where(Performance.status == PerformanceStatus.scheduled)
    return q


def upcoming_summary(db: Session, production_ids: list, now: datetime | None = None) -> dict:
    """{production_id: (count, next_performance)} for scheduled public upcoming performances."""
    if not production_ids:
        return {}
    now = now or utcnow()
    base = public_performances(now, include_cancelled=False).where(Performance.production_id.in_(production_ids))
    # One ordered query grouped in Python: the first row per production is its next performance.
    out: dict = {}
    for perf in db.scalars(base).unique():
        cnt, first = out.get(perf.production_id, (0, None))
        out[perf.production_id] = (cnt + 1, first or perf)
    return out


def search_productions(
    db: Session,
    *,
    q: str | None = None,
    genre: str | None = None,
    has_upcoming: bool | None = None,
    on_stage: bool | None = None,
) -> tuple[list[Production], dict]:
    stmt = public_productions()
    if genre:
        stmt = stmt.where(any_(Production.genres) == genre)
    if on_stage is not None:
        stmt = stmt.where(Production.on_stage.is_(on_stage))
    productions = list(db.scalars(stmt).unique())
    if q:
        needle = fold(q.strip())
        productions = [
            p for p in productions
            if needle in fold(" ".join([p.title, p.description or "", " ".join(c.name for c in p.credits),
                                         " ".join(p.genres or [])]))
        ]
    summary = upcoming_summary(db, [p.id for p in productions])
    if has_upcoming is not None:
        productions = [p for p in productions if (p.id in summary) == has_upcoming]

    # Order: soonest upcoming first, then "on stage" repertoire, then editorial order, then title.
    productions.sort(key=lambda p: (
        p.id not in summary,
        summary[p.id][1].starts_at.isoformat() if p.id in summary else "",
        not p.on_stage,
        p.sort_order,
        fold(p.title),
    ))
    return productions, summary


def genres(db: Session) -> list[str]:
    rows = db.scalars(
        select(func.unnest(Production.genres)).where(Production.status == PublicationStatus.published).distinct()
    ).all()
    return sorted({r for r in rows if r}, key=fold)
