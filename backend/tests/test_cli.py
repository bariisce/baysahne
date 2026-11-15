from datetime import timedelta

from app.cli import prune
from app.core.text import utcnow
from app.models import AuditLog, DevicePlatform, PushDevice


def test_prune_removes_only_old_records(db):
    old = utcnow() - timedelta(days=400)
    db.add_all([
        AuditLog(action="x.old", created_at=old),
        AuditLog(action="x.new"),
        PushDevice(installation_id="old-inactive-device-000", platform=DevicePlatform.ios, is_active=False, deactivated_at=old),
        PushDevice(installation_id="active-device-000000000", platform=DevicePlatform.ios, is_active=True,
                   push_token="ExponentPushToken[keep-me-1234567]"),
    ])
    db.commit()
    assert prune(deliveries_days=90, audit_days=365, devices_days=30, sessions_days=30) == 0
    db.expire_all()
    assert [a.action for a in db.query(AuditLog).all()] == ["x.new"]
    assert [d.installation_id for d in db.query(PushDevice).all()] == ["active-device-000000000"]
