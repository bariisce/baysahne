from sqlalchemy.orm import Session

from app.models import AdminUser, AuditLog


def record(
    db: Session,
    actor: AdminUser | None,
    action: str,
    *,
    entity_type: str | None = None,
    entity_id=None,
    summary: str | None = None,
    details: dict | None = None,
    ip: str | None = None,
) -> None:
    """Append an audit entry to the current transaction (committed together with the change itself)."""
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            summary=(summary or "")[:300] or None,
            details=details or {},
            ip=ip,
        )
    )
