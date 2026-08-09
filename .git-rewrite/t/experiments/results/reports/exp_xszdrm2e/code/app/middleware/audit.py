import logging
import json
import os
from datetime import datetime, timezone
from flask import g, request


audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)


def init_audit_logging(app):
    log_file = app.config.get("AUDIT_LOG_FILE", "audit.log")
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)

    @app.before_request
    def before_request_logging():
        g.request_start_time = datetime.now(timezone.utc)
        g.request_id = os.urandom(8).hex()

    @app.after_request
    def after_request_logging(response):
        duration_ms = None
        if hasattr(g, "request_start_time"):
            delta = datetime.now(timezone.utc) - g.request_start_time
            duration_ms = int(delta.total_seconds() * 1000)

        entry = json.dumps(
            {
                "request_id": getattr(g, "request_id", "-"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "remote_addr": request.remote_addr,
                "user_agent": request.headers.get("User-Agent", "-"),
            }
        )
        log_entry = json.dumps(entry)
        audit_logger.info(log_entry)
        return response
