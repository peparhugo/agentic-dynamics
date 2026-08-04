from __future__ import annotations

import logging
import time
from typing import Optional

from flask import Flask, g, request
from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


jwt = JWTManager()


def _rate_limit_key_func() -> str:
    """Use JWT identity when available; otherwise fallback to IP.
    This helps enforce per-user limits after authentication.
    """
    try:
        verify_jwt_in_request(optional=True)
        identity: Optional[str] = get_jwt_identity()
        if identity:
            return f"user:{identity}"
    except Exception:
        # If token missing/invalid, fall back to IP
        pass
    return f"ip:{get_remote_address()}"


# Do not set default_limits here so app.config[RATELIMIT_DEFAULT] is respected
limiter = Limiter(key_func=_rate_limit_key_func)


def audit_logger(app: Flask) -> logging.Logger:
    """Configure and return the audit logger.

    Important: tests create multiple app instances with different AUDIT_LOG_PATH values.
    We therefore always refresh handlers to point to the current app's path.
    """
    logger = logging.getLogger("audit")
    logger.setLevel(logging.INFO)
    # Remove existing handlers to avoid writing to stale paths across app instances
    for h in list(logger.handlers):
        try:
            h.close()
        finally:
            logger.removeHandler(h)

    handler = logging.FileHandler(app.config["AUDIT_LOG_PATH"])  # ASCII path
    fmt = logging.Formatter(
        fmt=(
            "%(asctime)s | %(levelname)s | method=%(method)s path=%(path)s "
            "status=%(status)s user=%(user)s ip=%(ip)s ua=%(ua)s dur_ms=%(dur_ms)s"
        )
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def init_audit_hooks(app: Flask) -> None:
    logger = audit_logger(app)

    @app.before_request
    def _audit_start():
        # Mark start time for duration
        g._start_time = time.perf_counter()

    @app.after_request
    def _audit_log(response):
        # Basic request/response audit. Avoid PII beyond essentials.
        duration_ms = int((time.perf_counter() - getattr(g, "_start_time", time.perf_counter())) * 1000)
        extra = {
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "user": None,
            "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
            "ua": request.headers.get("User-Agent", "-"),
            "dur_ms": duration_ms,
        }
        try:
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
            if identity:
                extra["user"] = identity
        except Exception:
            pass
        try:
            logger.info("request", extra=extra)
        except Exception:
            # Never let audit logging break request handling
            pass
        return response
