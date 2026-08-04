import functools
from datetime import datetime, timezone

from flask import request
from app.extensions import db
from app.models import AuditLog
from app.auth import get_current_user_or_none


def log_audit(action=None, resource=None):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            response = fn(*args, **kwargs)
            status_code = response[1] if isinstance(response, tuple) else response.status_code

            user = get_current_user_or_none()
            resource_id = kwargs.get("id") or kwargs.get("item_id") or kwargs.get("user_id")

            log_entry = AuditLog(
                user_id=user.id if user else None,
                action=action or request.method.lower(),
                resource=resource or request.endpoint or "unknown",
                resource_id=resource_id,
                method=request.method,
                path=request.path,
                ip_address=request.remote_addr,
                details={
                    "args": dict(request.args) if request.args else {},
                    "content_length": request.content_length,
                },
                status_code=status_code,
            )
            db.session.add(log_entry)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return response
        return wrapper
    return decorator


def log_audit_manual(user_id, action, resource, resource_id=None, method=None, path=None,
                     ip_address=None, details=None, status_code=None):
    try:
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            method=method or "UNKNOWN",
            path=path or request.path if request else "unknown",
            ip_address=ip_address or (request.remote_addr if request else None),
            details=details or {},
            status_code=status_code,
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
