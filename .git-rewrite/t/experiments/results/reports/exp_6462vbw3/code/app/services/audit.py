from flask import request, g
from app.extensions import db
from app.models.audit_log import AuditLog


def log_audit(action: str, resource: str, resource_id: int | None = None, details: str | None = None) -> None:
    user_id = getattr(g, "current_user", None)
    user_id = user_id.id if user_id else None
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)
    db.session.commit()
