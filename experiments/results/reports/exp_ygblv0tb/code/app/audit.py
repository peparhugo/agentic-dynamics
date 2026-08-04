import logging

from flask import request

from .extensions import db
from .models import AuditLog

logger = logging.getLogger("audit")


def record_audit(action, status_code, user_id=None, detail=None):
    """Persist an audit entry and emit a structured log line."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=request.path,
        method=request.method,
        status_code=status_code,
        ip_address=request.remote_addr,
        detail=detail,
    )
    db.session.add(entry)
    db.session.commit()
    logger.info(
        "audit action=%s method=%s resource=%s status=%s user_id=%s ip=%s",
        action, request.method, request.path, status_code, user_id,
        request.remote_addr,
    )
    return entry
