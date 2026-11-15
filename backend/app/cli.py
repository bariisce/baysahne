"""Operator commands (run on the server, never exposed over HTTP).

  python -m app.cli bootstrap-admin --email you@example.com --name "Ad Soyad"
      Creates a one-time invitation for the FIRST administrator and prints the link to this terminal.
      Refuses to run once any active admin exists (use the admin panel to invite further staff).

  python -m app.cli import-content [--source PATH] [--report PATH]
      Idempotent import of BAY SAHNE BİLGİLER.docx and its media.
"""

import argparse
import sys

from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import AdminRole, AdminUser
from app.services import auth as auth_service


def bootstrap_admin(email: str, name: str, force: bool) -> int:
    from email_validator import EmailNotValidError, validate_email

    try:
        # Same rules the login endpoint applies, so the account can actually sign in.
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as e:
        print(f"Invalid e-mail address: {e}", file=sys.stderr)
        return 2
    if not name.strip():
        print("Name is required.", file=sys.stderr)
        return 2
    db = SessionLocal()
    try:
        admins = db.scalar(select(func.count()).select_from(AdminUser).where(
            AdminUser.role == AdminRole.admin, AdminUser.is_active.is_(True)))
        if admins and not force:
            print("An active administrator already exists. Invite staff from the admin panel instead.",
                  file=sys.stderr)
            return 1
        inv, raw = auth_service.create_invitation(db, email=email, full_name=name, role=AdminRole.admin,
                                                  invited_by=None)
        db.commit()
        hours = get_settings().invitation_ttl_hours
        print("One-time administrator invitation created.")
        print(f"  E-mail : {inv.email}\n  Expires: in {hours} hours")
        print(f"  Link   : {auth_service.invitation_link(raw)}")
        print("Open the link in a browser to set the password. It cannot be shown again.")
        return 0
    finally:
        db.close()


def prune(deliveries_days: int, audit_days: int, devices_days: int, sessions_days: int) -> int:
    """Delete operational records older than the given ages. The ages are a policy decision for the
    organisation (see docs/LEGAL_REVIEW.md); there are deliberately no defaults."""
    from datetime import timedelta

    from sqlalchemy import delete, or_

    from app.core.text import utcnow
    from app.models import AdminSession, AuditLog, NotificationDelivery, PasswordResetToken, PushDevice

    now = utcnow()
    db = SessionLocal()
    try:
        n_del = db.execute(delete(NotificationDelivery).where(
            NotificationDelivery.created_at < now - timedelta(days=deliveries_days))).rowcount
        n_audit = db.execute(delete(AuditLog).where(AuditLog.created_at < now - timedelta(days=audit_days))).rowcount
        n_dev = db.execute(delete(PushDevice).where(
            PushDevice.is_active.is_(False), PushDevice.deactivated_at < now - timedelta(days=devices_days))).rowcount
        n_sess = db.execute(delete(AdminSession).where(or_(
            AdminSession.expires_at < now - timedelta(days=sessions_days),
            AdminSession.revoked_at < now - timedelta(days=sessions_days)))).rowcount
        n_tok = db.execute(delete(PasswordResetToken).where(
            PasswordResetToken.expires_at < now - timedelta(days=sessions_days))).rowcount
        db.commit()
        print(f"Pruned: {n_del} deliveries, {n_audit} audit entries, {n_dev} inactive devices, "
              f"{n_sess} sessions, {n_tok} reset tokens.")
        return 0
    finally:
        db.close()


def main() -> int:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("prune", help="delete old operational records (retention)")
    pr.add_argument("--deliveries-days", type=int, required=True)
    pr.add_argument("--audit-days", type=int, required=True)
    pr.add_argument("--devices-days", type=int, required=True, help="inactive devices only")
    pr.add_argument("--sessions-days", type=int, required=True)
    b = sub.add_parser("bootstrap-admin")
    b.add_argument("--email", required=True)
    b.add_argument("--name", required=True)
    b.add_argument("--force", action="store_true", help="allow even if an admin exists (break-glass)")
    i = sub.add_parser("import-content")
    i.add_argument("--source", default=None,
                   help="folder holding the .docx, with the images anywhere below it (default: <repo>/content)")
    i.add_argument("--report", default=None, help="where to write the Markdown import report")
    args = p.parse_args()
    if args.cmd == "bootstrap-admin":
        return bootstrap_admin(args.email, args.name, args.force)
    if args.cmd == "prune":
        return prune(args.deliveries_days, args.audit_days, args.devices_days, args.sessions_days)
    if args.cmd == "import-content":
        from app.importer.run import main as run_import

        return run_import(args.source, args.report)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
