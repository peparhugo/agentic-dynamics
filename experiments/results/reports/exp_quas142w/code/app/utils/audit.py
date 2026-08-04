import logging
import json
from datetime import datetime, timezone
from flask import request, g


_audit_logger = None


def get_audit_logger():
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = logging.getLogger("audit")
        _audit_logger.setLevel(logging.INFO)
        _audit_logger.propagate = False
    return _audit_logger


def setup_audit_logger(app):
    logger = get_audit_logger()
    if logger.handlers:
        return

    log_file = app.config.get("AUDIT_LOG_FILE")
    if log_file:
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)


def log_audit(action, resource, resource_id=None, details=None, status="success"):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "status": status,
        "ip": request.remote_addr,
        "method": request.method,
        "path": request.path,
        "details": details or {},
        "user": getattr(g, "current_user", None),
    }
    get_audit_logger().info(json.dumps(entry))
