"""Structured audit logging.

Emits one JSON line per auditable event to the `audit` logger. Events carry
a request id (also returned to clients via the X-Request-ID header).
"""
import json
import logging
import uuid
from datetime import datetime, timezone

from flask import g, request

logger = logging.getLogger("audit")


def init_audit(app):
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    log_file = app.config.get("AUDIT_LOG_FILE")
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(fh)

    @app.before_request
    def assign_request_id():
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

    @app.after_request
    def attach_request_id(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "-")
        return response


def audit(action: str, *, status: str = "success", target: str = None, **extra):
    """Record an auditable event for the current request."""
    user = getattr(g, "current_user", None)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": getattr(g, "request_id", None),
        "action": action,
        "status": status,
        "actor": user["id"] if user else None,
        "actor_email": user["email"] if user else None,
        "target": target,
        "ip": request.remote_addr,
        "method": request.method,
        "path": request.path,
        **extra,
    }
    logger.info(json.dumps(event, default=str))
    return event
