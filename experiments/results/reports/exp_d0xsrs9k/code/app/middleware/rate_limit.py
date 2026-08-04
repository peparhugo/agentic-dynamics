import functools
import threading
import time
from collections import defaultdict

from flask import jsonify, request, current_app


class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._windows: dict[str, list[float]] = defaultdict(list)

    def is_rate_limited(self, key: str, limit: int, period: int) -> bool:
        now = time.monotonic()
        with self._lock:
            window = self._windows[key]
            window[:] = [t for t in window if now - t < period]
            if len(window) >= limit:
                return True
            window.append(now)
            return False

    def reset(self):
        with self._lock:
            self._windows.clear()


_rate_limiter = RateLimiter()


def get_rate_limit_key() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return f"token:{hash(auth) % 100000}"
    return f"ip:{request.remote_addr}"


def rate_limit(limit_str: str | None = None):
    """Decorator that rate limits an endpoint.

    limit_str format: "N per minute" or "N per second"
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            effective_limit = limit_str or current_app.config.get("RATE_LIMIT_DEFAULT", "100 per minute")
            parts = effective_limit.split()
            if len(parts) != 3 or parts[1] != "per":
                return f(*args, **kwargs)

            try:
                n = int(parts[0])
            except ValueError:
                return f(*args, **kwargs)

            unit = parts[2].lower()
            period_map = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
            period = period_map.get(unit, 60)

            endpoint = request.endpoint or request.path
            key = f"{endpoint}:{get_rate_limit_key()}"

            if _rate_limiter.is_rate_limited(key, limit=n, period=period):
                return jsonify({
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded: {limit_str}",
                }), 429

            return f(*args, **kwargs)

        return decorated

    return decorator


def reset_rate_limiter():
    _rate_limiter.reset()
