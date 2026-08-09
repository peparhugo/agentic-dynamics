import json
import logging
from datetime import datetime, timezone

from flask import current_app, g, request

audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)


def _has_handler():
    return len(audit_logger.handlers) > 0


def log_event(action, resource=None, resource_id=None, status_code=None, details=None):

    if not current_app.config.get("LOG_FILE"):
        return

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "user_id": g.current_user.id if g.get("current_user") else None,
        "ip": request.remote_addr,
        "method": request.method,
        "path": request.path,
        "status_code": status_code,
        "details": details,
    }
    audit_logger.info(json.dumps(entry))


def setup_audit_logging(app):
    if not app.config.get("LOG_FILE"):
        return

    handler = logging.FileHandler(app.config["LOG_FILE"])
    handler.setFormatter(
        logging.Formatter("%(message)s")
    )
    audit_logger.addHandler(handler)
