import logging
from functools import wraps
from flask import request, g
import time


logger = logging.getLogger("audit")


def audit_log(action):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            start = time.time()
            user = getattr(g, "current_user", None)
            user_id = user.id if user else None
            response, status_code = f(*args, **kwargs)
            duration_ms = int((time.time() - start) * 1000)
            logger.info(
                f"user_id={user_id} method={request.method} path={request.path} "
                f"action={action} status={status_code} duration_ms={duration_ms}"
            )
            return response, status_code
        return wrapper
    return decorator
