import time
import threading
from functools import wraps
from flask import request, current_app, jsonify


_lock = threading.Lock()
_buckets: dict[str, tuple[int, int]] = {}


def _now() -> int:
    return int(time.time())


def _key() -> str:
    # Prefer authenticated user id when available; else IP
    uid = getattr(request, "user_id", None)
    if uid:
        return f"u:{uid}"
    return f"ip:{request.headers.get('X-Forwarded-For', request.remote_addr)}"


def rate_limited(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        limit = int(current_app.config.get("RATE_LIMIT_PER_WINDOW", 100))
        window = int(current_app.config.get("RATE_LIMIT_WINDOW_SECONDS", 60))
        key = _key()
        now = _now()
        with _lock:
            window_start, count = _buckets.get(key, (now, 0))
            # Move window if expired
            if now - window_start >= window:
                window_start, count = now, 0
            if count >= limit:
                reset = window_start + window - now
                resp = jsonify({"error": "rate_limited", "message": "Too many requests"})
                resp.headers["X-RateLimit-Limit"] = str(limit)
                resp.headers["X-RateLimit-Remaining"] = "0"
                resp.headers["X-RateLimit-Reset"] = str(reset)
                # Attach reset for error handler compatibility
                err = type("RateLimitError", (), {"description": "Too many requests", "reset": reset})()
                return current_app.handle_user_exception(err)
            count += 1
            _buckets[key] = (window_start, count)
            remaining = max(0, limit - count)
        resp = fn(*args, **kwargs)
        # Add rate limit headers
        try:
            flask_resp = resp if hasattr(resp, "headers") else None
            if flask_resp is None:
                # Convert (data, status) tuples by letting Flask jsonify in route
                pass
            else:
                flask_resp.headers["X-RateLimit-Limit"] = str(limit)
                flask_resp.headers["X-RateLimit-Remaining"] = str(remaining)
                flask_resp.headers["X-RateLimit-Reset"] = str(max(0, window_start + window - now))
        except Exception:
            # Don't let header issues break the endpoint
            pass
        return resp

    return wrapper
