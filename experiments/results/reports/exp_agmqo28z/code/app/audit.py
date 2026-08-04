from flask import request, g
from app import db
from app.models import AuditLog


def log_audit(action, resource, resource_id=None, details=None):
    user_id = getattr(g, "current_user_id", None)
    ip = request.remote_addr if request else None
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=str(details) if details else None,
        ip_address=ip,
    )
    db.session.add(entry)
    db.session.flush()
