"""Audit logging: persisted to the audit_log table and mirrored to a logger."""
import logging

from flask import g, request

from .db import get_db

logger = logging.getLogger("audit")


def audit(action: str, resource: str = None, status: int = 200, detail: str = None,
          actor_id=None):
    """Record an auditable event for the current request."""
    if actor_id is None:
        user = getattr(g, "current_user", None)
        actor_id = user["id"] if user is not None else None
    ip = request.remote_addr if request else None
    db = get_db()
    db.execute(
        "INSERT INTO audit_log (actor_id, action, resource, status, ip, detail) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (actor_id, action, resource, status, ip, detail),
    )
    db.commit()
    logger.info(
        "action=%s resource=%s status=%s actor=%s ip=%s detail=%s",
        action, resource, status, actor_id, ip, detail,
    )
