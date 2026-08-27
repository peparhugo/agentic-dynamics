from .extensions import db
from .models import AuditLog


def log_audit(action, resource, resource_id=None, user_id=None, details=None):
    entry = AuditLog(
        action=action,
        resource=resource,
        resource_id=resource_id,
        user_id=user_id,
        details=details,
    )
    db.session.add(entry)
    return entry
