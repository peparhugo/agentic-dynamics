from flask import request, g
from flask_jwt_extended import current_user
import structlog
import time
import functools

logger = structlog.get_logger()


def register_audit_logging(app):
    @app.before_request
    def log_request():
        g.request_start_time = time.time()
        g.request_id = request.headers.get("X-Request-ID", "")

    @app.after_request
    def log_response(response):
        elapsed = time.time() - g.get("request_start_time", time.time())
        user_id = None
        try:
            user_id = current_user.id if current_user else None
        except Exception:
            pass

        logger.info(
            "api_request",
            method=request.method,
            path=request.path,
            status=response.status_code,
            elapsed_ms=round(elapsed * 1000, 2),
            user_id=user_id,
            remote_addr=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )
        return response


def audit_action(action, detail=None):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            result = f(*args, **kwargs)
            user_id = None
            try:
                user_id = current_user.id if current_user else None
            except Exception:
                pass

            logger.info(
                "audit_event",
                action=action,
                detail=detail,
                user_id=user_id,
                path=request.path,
                method=request.method,
            )
            return result
        return wrapper
    return decorator
