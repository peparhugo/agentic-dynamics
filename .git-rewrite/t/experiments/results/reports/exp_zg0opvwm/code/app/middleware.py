from app import db
from app.models import AuditLog


def log_audit(user_id, action, resource, resource_id=None, details=None, request=None):
    ip_address = request.remote_addr if request else None
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        ip_address=ip_address,
        details=details,
    )
    db.session.add(entry)
    db.session.commit()
