import json
import time
import logging
from flask import request, g, current_app, has_request_context

_audit_logger = logging.getLogger("audit")
_audit_logger.setLevel(logging.INFO)
_handler = None


def _get_handler():
    global _handler
    if _handler is None:
        from flask import current_app as app
        log_file = app.config.get("AUDIT_LOG_FILE", "audit.log")
        _handler = logging.FileHandler(log_file)
        _handler.setFormatter(logging.Formatter('%(message)s'))
        _audit_logger.handlers = [_handler]
    return _handler


def log_audit(action: str, resource: str, details: dict = None, resource_id: str = None):
    if not has_request_context():
        return

    entry = {
        "timestamp": time.time(),
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "user_id": getattr(g, "current_user_id", None),
        "ip": request.remote_addr,
        "method": request.method,
        "path": request.path,
        "details": details or {},
    }

    _get_handler()
    _audit_logger.info(json.dumps(entry))


def audit_log(action_override: str = None, resource_override: str = None):
    def decorator(f):
        def wrapper(*args, **kwargs):
            result = f(*args, **kwargs)

            status_code = 200
            if isinstance(result, tuple):
                status_code = result[1]

            if 200 <= status_code < 400:
                action = action_override or _action_from_method()
                resource = resource_override or _resource_from_path()
                res_id = kwargs.get("user_id") or kwargs.get("id")
                log_audit(action, resource, resource_id=res_id)

            return result

        return wrapper

    return decorator


def _action_from_method() -> str:
    mapping = {
        "GET": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }
    return mapping.get(request.method, "unknown")


def _resource_from_path() -> str:
    parts = [p for p in request.path.strip("/").split("/") if p]
    if len(parts) >= 2 and parts[0] == "api":
        parts = parts[1:]
    return parts[0] if parts else "unknown"
