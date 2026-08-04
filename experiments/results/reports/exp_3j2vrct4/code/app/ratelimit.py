"""Fixed-window in-memory rate limiter.

Suitable for a single-process deployment; swap the storage for Redis in a
multi-process setup (the interface is a single `hit()` call).
"""
import functools
import threading
import time

from flask import current_app, g, request

from .errors import RateLimitError


class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters = {}  # (key, window_start) -> count

    def reset(self):
        with self._lock:
            self._counters.clear()

    def hit(self, key: str, limit: int, window: int):
        """Record a hit. Returns (allowed, remaining, retry_after)."""
        now = time.time()
        window_start = int(now // window) * window
        bucket = (key, window_start)
        with self._lock:
            # Drop expired buckets to bound memory.
            self._counters = {
                k: v for k, v in self._counters.items() if k[1] >= window_start - window
            }
            count = self._counters.get(bucket, 0) + 1
            self._counters[bucket] = count
        remaining = max(0, limit - count)
        retry_after = int(window_start + window - now) + 1
        return count <= limit, remaining, retry_after


def _client_key() -> str:
    user = getattr(g, "current_user", None)
    if user is not None:
        return f"user:{user['id']}"
    return f"ip:{request.remote_addr or 'unknown'}"


def rate_limit(limit=None, window=None, scope="default"):
    """Decorator applying a fixed-window rate limit to a view."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            cfg = current_app.config
            if not cfg.get("RATELIMIT_ENABLED", True):
                return fn(*args, **kwargs)
            lim = limit if limit is not None else cfg["RATELIMIT_DEFAULT_LIMIT"]
            win = window if window is not None else cfg["RATELIMIT_DEFAULT_WINDOW"]
            limiter: RateLimiter = current_app.extensions["rate_limiter"]
            key = f"{scope}:{_client_key()}"
            allowed, remaining, retry_after = limiter.hit(key, lim, win)
            g.ratelimit_headers = {
                "X-RateLimit-Limit": str(lim),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(retry_after),
            }
            if not allowed:
                raise RateLimitError(
                    details={"retry_after": retry_after, "limit": lim, "window": win}
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def init_app(app):
    app.extensions["rate_limiter"] = RateLimiter()

    @app.after_request
    def attach_headers(response):
        for name, value in getattr(g, "ratelimit_headers", {}).items():
            response.headers[name] = value
        return response
