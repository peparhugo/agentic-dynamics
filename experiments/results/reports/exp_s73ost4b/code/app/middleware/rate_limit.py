import time
from collections import defaultdict
from functools import wraps

from flask import request, jsonify, g
from app.config import Config


_rate_window_starts = defaultdict(lambda: {"window_start": 0.0, "count": 0})


def get_rate_limit_key():
    auth = request.headers.get("Authorization", "")
    ip = request.remote_addr or "127.0.0.1"
    return f"{ip}:{auth[:20]}"


def rate_limit(max_requests=None, window_seconds=None):
    max_requests = max_requests or Config.RATE_LIMIT_DEFAULT
    window_seconds = window_seconds or Config.RATE_LIMIT_WINDOW

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if g.get("_rate_limit_disabled"):
                return fn(*args, **kwargs)

            key = get_rate_limit_key()
            now = time.time()

            entry = _rate_window_starts[key]
            if now - entry["window_start"] >= window_seconds:
                entry["window_start"] = now
                entry["count"] = 0

            entry["count"] += 1

            remaining = max(0, max_requests - entry["count"])
            reset_at = int(entry["window_start"] + window_seconds)

            if entry["count"] > max_requests:
                resp = jsonify({"error": "Rate limit exceeded. Try again later."})
                resp.status_code = 429
                resp.headers["Retry-After"] = str(reset_at - int(now))
                resp.headers["X-RateLimit-Limit"] = str(max_requests)
                resp.headers["X-RateLimit-Remaining"] = "0"
                resp.headers["X-RateLimit-Reset"] = str(reset_at)
                return resp

            response = fn(*args, **kwargs)
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_at)
            return response

        return wrapper

    return decorator
