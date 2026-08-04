import json
from flask import request, has_request_context
from app.extensions import db
from app.models.audit_log import AuditLog


def log_audit(action, resource_type, resource_id=None, details=None, user_id=None):
    if not has_request_context():
        return

    ip_address = request.remote_addr if request else None

    detail_str = None
    if details is not None:
        if isinstance(details, dict):
            detail_str = json.dumps(details, default=str)
        else:
            detail_str = str(details)

    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=detail_str,
        ip_address=ip_address,
    )
    db.session.add(log_entry)
