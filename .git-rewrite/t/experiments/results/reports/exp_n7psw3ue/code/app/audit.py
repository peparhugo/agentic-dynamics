from app import db
from app.models import AuditLog


def log_audit(user_id, action, resource, resource_id=None, details=None, ip_address=None):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    db.session.add(entry)
