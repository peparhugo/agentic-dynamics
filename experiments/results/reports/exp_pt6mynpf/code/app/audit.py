"""Audit logging.

Every security-relevant event (auth attempts, resource mutations) is written
to the `audit_logs` table. Failures to write an audit record never break the
request; they are logged to the application logger instead.
"""
from flask import current_app, request

from app.extensions import db
from app.models import AuditLog


def audit(action: str, *, user_id=None, resource_type=None, resource_id=None,
          status_code=None, detail=None) -> None:
    try:
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
        db.session.commit()
    except Exception:  # pragma: no cover - defensive
        db.session.rollback()
        current_app.logger.exception("Failed to write audit log for action=%s", action)
