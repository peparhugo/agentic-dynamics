import time
from functools import wraps
from flask import request, g, current_app


_rate_store: dict[str, list[float]] = {}


def rate_limit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        key = _build_key()
        max_req = current_app.config.get("RATE_LIMIT_REQUESTS", 100)
        window = current_app.config.get("RATE_LIMIT_WINDOW", 60)

        now = time.monotonic()
        timestamps = _rate_store.get(key, [])
        timestamps = [t for t in timestamps if now - t < window]
        _rate_store[key] = timestamps

        if len(timestamps) >= max_req:
            retry_after = int(window - (now - timestamps[0]))
            return {
                "error": "Rate limit exceeded",
                "code": "RATE_LIMITED",
                "retry_after": retry_after,
            }, 429

        _rate_store[key].append(now)
        return f(*args, **kwargs)

    return wrapper


def _build_key() -> str:
    user_id = getattr(g, "current_user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{request.remote_addr}"


def _clear_rate_store():
    _rate_store.clear()
