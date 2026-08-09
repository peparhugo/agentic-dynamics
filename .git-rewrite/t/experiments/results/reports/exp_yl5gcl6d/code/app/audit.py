"""Audit logging helpers."""
from flask import g, request

from .extensions import db
from .models import AuditLog


def audit(action: str, *, resource_type: str | None = None,
          resource_id=None, status_code: int | None = None,
          detail: str | None = None, user_id: int | None = None) -> AuditLog:
    """Record an audit event. Committed with the surrounding transaction."""
    if user_id is None:
        user = getattr(g, "current_user", None)
        user_id = user.id if user is not None else None

    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=request.remote_addr if request else None,
        method=request.method if request else None,
        path=request.path if request else None,
        status_code=status_code,
        detail=detail,
    )
    db.session.add(entry)
    return entry
