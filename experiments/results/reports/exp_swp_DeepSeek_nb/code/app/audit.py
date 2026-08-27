import json

from flask import request

from .extensions import db
from .models import AuditLog


def log_action(user_id, action, resource, resource_id=None, details=None):
    ip = request.remote_addr if request else None
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=ip,
        details=json.dumps(details) if details is not None else None,
    )
    db.session.add(entry)
    return entry
