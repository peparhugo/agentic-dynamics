"""Simple in-memory fixed-window rate limiter.

Suitable for a single-process deployment; swap the storage for Redis in a
multi-process setup (the interface is deliberately tiny).

Adds standard headers to responses:
    X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
and raises RateLimitError (429 + Retry-After) when exceeded.
"""
import threading
import time
from functools import wraps

from flask import current_app, g, request

from .errors import RateLimitError


class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}  # key -> (window_start, count)

    def reset(self):
        with self._lock:
            self._windows.clear()

    def hit(self, key: str, limit: int, window: int, now: float | None = None):
        """Record a hit. Returns (allowed, remaining, reset_epoch)."""
        now = time.time() if now is None else now
        window_start = int(now // window) * window
        with self._lock:
            start, count = self._windows.get(key, (window_start, 0))
            if start != window_start:
                start, count = window_start, 0
            count += 1
            self._windows[key] = (start, count)
        reset = window_start + window
        allowed = count <= limit
        remaining = max(0, limit - count)
        return allowed, remaining, reset


limiter = RateLimiter()


def _client_key() -> str:
    """Prefer the authenticated user identity; fall back to remote address."""
    user = getattr(g, "current_user", None)
    if user is not None:
        return f"user:{user.id}"
    return f"ip:{request.remote_addr or 'unknown'}"


def rate_limit(limit_config_key: str = "RATELIMIT_DEFAULT_LIMIT",
               window_config_key: str = "RATELIMIT_DEFAULT_WINDOW"):
    """Decorator applying a fixed-window limit per client per endpoint."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            cfg = current_app.config
            if not cfg.get("RATELIMIT_ENABLED", True):
                return fn(*args, **kwargs)

            limit = cfg[limit_config_key]
            window = cfg[window_config_key]
            key = f"{request.endpoint}:{_client_key()}"
            allowed, remaining, reset = limiter.hit(key, limit, window)

            g.rate_limit_headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset),
            }
            if not allowed:
                retry_after = max(1, int(reset - time.time()))
                raise RateLimitError(
                    "Rate limit exceeded. Try again later.",
                    retry_after=retry_after,
                    details={"limit": limit, "window_seconds": window},
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def install_rate_limit_headers(app):
    @app.after_request
    def add_headers(response):
        for name, value in getattr(g, "rate_limit_headers", {}).items():
            response.headers[name] = value
        return response
