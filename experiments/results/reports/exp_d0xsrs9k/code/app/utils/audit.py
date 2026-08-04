import logging
import sys
import json
from datetime import datetime, timezone

import flask

AUDIT_FIELDS = frozenset({
    "audit_type", "user_id", "email", "method", "path",
    "status_code", "ip", "user_agent", "duration_ms", "request_id",
})


class AuditFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for field in AUDIT_FIELDS:
            value = getattr(record, field, record.__dict__.get(field))
            if value is not None:
                entry[field] = value
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra", {})
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k not in AUDIT_FIELDS and k not in ("message", "level", "timestamp"):
                    entry[k] = v
        return json.dumps(entry, default=str)


def setup_audit_logging(app: flask.Flask):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(AuditFormatter())
    handler.setLevel(logging.INFO)

    audit_logger = logging.getLogger("audit")
    audit_logger.handlers.clear()
    audit_logger.addHandler(handler)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False


def log_request(g: flask.g, response: flask.Response):
    """Log API request details after each request."""
    import logging
    logger = logging.getLogger("audit")
    duration = getattr(g, "request_start_time", None)
    if duration is not None:
        duration = (datetime.now(timezone.utc) - duration).total_seconds() * 1000

    logger.info(
        "API request",
        extra={
            "audit_type": "api_request",
            "method": flask.request.method,
            "path": flask.request.path,
            "status_code": response.status_code if hasattr(response, "status_code") else response.status,
            "ip": flask.request.remote_addr,
            "user_agent": flask.request.headers.get("User-Agent", ""),
            "duration_ms": round(duration, 2) if duration else None,
            "request_id": getattr(g, "request_id", None),
            "user_id": getattr(getattr(g, "current_user", None), "id", None),
        },
    )
    return response
