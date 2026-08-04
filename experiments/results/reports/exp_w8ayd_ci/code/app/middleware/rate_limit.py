from functools import wraps
import time

from flask import request, g
from werkzeug.http import parse_dict_header

_local_limits = {}


def dynamic_rate_limit(limit_per_window=100, window_seconds=3600):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            key = _build_key(f"{f.__module__}.{f.__qualname__}")
            now = time.time()
            record = _local_limits.get(key, {"count": 0, "reset": now + window_seconds})

            if now >= record["reset"]:
                record = {"count": 1, "reset": now + window_seconds}
            else:
                record["count"] += 1

            _local_limits[key] = record

            remaining = max(0, limit_per_window - record["count"])
            reset_ts = int(record["reset"])

            headers = {
                "X-RateLimit-Limit": str(limit_per_window),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_ts),
            }
            g.ratelimit_headers = headers

            if record["count"] > limit_per_window:
                from app.utils.errors import RateLimitError
                raise RateLimitError(
                    message="Too many requests",
                    details={
                        "limit": limit_per_window,
                        "remaining": 0,
                        "reset": reset_ts,
                    },
                )

            response = f(*args, **kwargs)
            return response

        return decorated

    return decorator


def _build_key(identity):
    return f"rl:local:{identity}"


def get_remote_address_key():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"
