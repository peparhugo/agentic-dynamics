import json

from flask import request

from .extensions import db
from .models import AuditLog


def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.environ.get("REMOTE_ADDR") or request.remote_addr


def log_action(action, resource_type, resource_id=None, user_id=None, details=None):
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            ip_address=get_client_ip(),
            details=json.dumps(details) if details is not None else None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
