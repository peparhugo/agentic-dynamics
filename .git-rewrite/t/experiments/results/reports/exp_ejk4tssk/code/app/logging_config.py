import logging
from logging.handlers import RotatingFileHandler
from flask import request, g
import time

def configure_audit_logging(app):
    handler = RotatingFileHandler("audit.log", maxBytes=10_000_00, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)

    @app.before_request
    def _start_timer():
        g._start_time = time.time()

    @app.after_request
    def _audit_log(response):
        try:
            duration = (time.time() - g._start_time) * 1000
        except Exception:
            duration = 0
        user = getattr(g, "current_user", None)
        app.logger.info(
            "audit user=%s method=%s path=%s status=%s duration_ms=%.2f",
            user or "-",
            request.method,
            request.path,
            response.status_code,
            duration,
        )
        return response
