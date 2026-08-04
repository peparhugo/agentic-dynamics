from flask import request, g
from app.models import AuditLog

_audit_queue = []


def log_audit(action, resource, resource_id=None, details=None):
    user_id = None
    try:
        user_id = g.current_user.id if g.current_user else None
    except Exception:
        user_id = None
    ip = request.remote_addr if request else None
    entry = {
        "user_id": user_id,
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "details": details,
        "ip_address": ip,
    }
    _audit_queue.append(entry)


def flush_audit_logs():
    from app import db
    for entry in _audit_queue:
        al = AuditLog(**entry)
        db.session.add(al)
    _audit_queue.clear()
