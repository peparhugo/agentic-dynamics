from flask import request
from app import db
from app.models.audit_log import AuditLog


def log_audit_event(
    action: str,
    user_id: int | None = None,
    resource: str | None = None,
    resource_id: str | None = None,
    details: str | None = None,
    status_code: int | None = None,
) -> None:
    try:
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")[:256],
            details=details,
            status_code=status_code,
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
