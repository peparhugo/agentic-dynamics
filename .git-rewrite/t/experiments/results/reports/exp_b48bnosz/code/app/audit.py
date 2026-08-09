"""Audit logging.

Two mechanisms:
1. An after_request hook that records every mutating request (POST/PUT/PATCH/DELETE)
   and auth-sensitive GETs under /api/.
2. `set_audit_action(action, detail)` for handlers to attach a semantic action name.
"""
from flask import Flask, g, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from .extensions import db
from .models import AuditLog

AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def set_audit_action(action: str, detail: str | None = None) -> None:
    g.audit_action = action
    g.audit_detail = detail


def _current_user_id():
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        return int(identity) if identity is not None else None
    except Exception:
        return None


def register_audit_hooks(app: Flask) -> None:
    @app.after_request
    def write_audit_log(response):
        if request.method not in AUDITED_METHODS or not request.path.startswith("/api/"):
            return response
        try:
            entry = AuditLog(
                user_id=_current_user_id(),
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                remote_addr=request.remote_addr,
                action=g.get("audit_action"),
                detail=g.get("audit_detail"),
            )
            db.session.add(entry)
            db.session.commit()
        except Exception:  # pragma: no cover - audit failure must not break responses
            app.logger.exception("Failed to write audit log")
            db.session.rollback()
        return response
