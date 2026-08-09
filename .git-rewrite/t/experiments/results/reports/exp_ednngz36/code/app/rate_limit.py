"""Fixed-window in-memory rate limiter.

Keys on authenticated user id when available, else remote address.
Sets standard X-RateLimit-* headers on every response and returns 429
with Retry-After when exceeded. Swap for Redis in production by
replacing RateLimiter with a Redis-backed implementation.
"""
import threading
import time

from flask import current_app, g, request

from .errors import RateLimitError


class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._windows = {}  # key -> (window_start, count)

    def hit(self, key, limit, window_seconds, now=None):
        """Record a hit. Returns (allowed, remaining, reset_epoch)."""
        now = now if now is not None else time.time()
        window_start = int(now // window_seconds) * window_seconds
        reset = window_start + window_seconds
        with self._lock:
            start, count = self._windows.get(key, (window_start, 0))
            if start != window_start:
                count = 0
            count += 1
            self._windows[key] = (window_start, count)
        remaining = max(0, limit - count)
        return count <= limit, remaining, reset

    def reset(self):
        with self._lock:
            self._windows.clear()


def _client_key():
    user = getattr(g, "current_user", None)
    if user:
        return f"user:{user['id']}"
    return f"ip:{request.remote_addr or 'unknown'}"


def install_rate_limiting(app, limiter):
    @app.before_request
    def _check_rate_limit():
        cfg = app.config
        if not cfg.get("RATE_LIMIT_ENABLED", True):
            return
        if request.endpoint in (None, "static"):
            return
        # Stricter bucket for auth endpoints to slow brute-forcing.
        is_auth = (request.endpoint or "").startswith("api_v1.auth_")
        limit = cfg["RATE_LIMIT_AUTH_REQUESTS"] if is_auth else cfg["RATE_LIMIT_REQUESTS"]
        bucket = "auth" if is_auth else "api"
        key = f"{bucket}:{_client_key()}"
        allowed, remaining, reset = limiter.hit(key, limit, cfg["RATE_LIMIT_WINDOW_SECONDS"])
        g.rate_limit_state = (limit, remaining, reset)
        if not allowed:
            retry_after = max(1, int(reset - time.time()))
            raise RateLimitError(
                "Rate limit exceeded. Try again later.",
                details={"retry_after": retry_after, "limit": limit},
            )

    @app.after_request
    def _set_rate_limit_headers(response):
        state = getattr(g, "rate_limit_state", None)
        if state:
            limit, remaining, reset = state
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(reset))
        return response
