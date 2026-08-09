import logging
import time
from flask import request, g, current_app
from app.models import AuditLog
from app import db

audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)


def configure_audit(app):
    handler = logging.FileHandler(app.config["AUDIT_LOG_FILE"])
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    audit_logger.addHandler(handler)

    @app.before_request
    def _start_timer():
        g.start_time = time.time()

    @app.after_request
    def _log_audit(response):
        if request.endpoint is None:
            return response

        duration = (time.time() - g.get("start_time", time.time())) * 1000
        user_id = getattr(g, "user_id", None)
        username = getattr(g, "username", None)

        body = None
        if request.method in ("POST", "PUT", "PATCH"):
            body = request.get_data(as_text=True)[:4096]

        audit_logger.info(
            "user=%s method=%s path=%s status=%d ip=%s duration=%.2fms",
            username or "anonymous",
            request.method,
            request.path,
            response.status_code,
            request.remote_addr,
            duration,
        )

        try:
            entry = AuditLog(
                user_id=user_id,
                username=username,
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                ip_address=request.remote_addr,
                request_body=body,
                response_size=response.content_length,
                duration_ms=round(duration, 2),
            )
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

        return response
