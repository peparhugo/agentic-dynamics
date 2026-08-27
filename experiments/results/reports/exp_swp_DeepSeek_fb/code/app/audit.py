import json

from flask import g, request

from .extensions import db
from .models import AuditLog


def record_audit(action, resource_type, resource_id=None, details=None):
    user = getattr(g, "current_user", None)
    user_id = user.id if user is not None else None
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        details=json.dumps(details) if details else None,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)
    return entry
