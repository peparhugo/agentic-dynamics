import json
import logging
import threading
import time
import os

from flask import request, g, current_app

_audit_lock = threading.Lock()

audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

_stream_handler = None


def _ensure_handler(app):
    global _stream_handler
    if _stream_handler is None:
        log_file = app.config.get("AUDIT_LOG_FILE", "audit.log")
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        audit_logger.addHandler(handler)
        _stream_handler = handler


def log_audit_event(action, resource, details=None, user_id=None, status="success"):
    app = current_app._get_current_object()
    _ensure_handler(app)

    event = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "action": action,
        "resource": resource,
        "status": status,
        "user_id": user_id or (g.get("current_user_id") if hasattr(g, "current_user_id") else None),
        "ip": (request.remote_addr if request else None),
        "method": (request.method if request else None),
        "path": (request.path if request else None),
    }
    if details:
        event["details"] = details

    with _audit_lock:
        audit_logger.info(json.dumps(event))


def audit_request(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        start = time.time()
        try:
            result = f(*args, **kwargs)
            duration_ms = int((time.time() - start) * 1000)
            log_audit_event(
                action=request.method,
                resource=request.path,
                details={"duration_ms": duration_ms},
            )
            return result
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            log_audit_event(
                action=request.method,
                resource=request.path,
                details={"duration_ms": duration_ms, "error": str(e)},
                status="failure",
            )
            raise

    return decorated
