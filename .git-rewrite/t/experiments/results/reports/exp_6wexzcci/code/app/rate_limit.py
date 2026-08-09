"""Sliding-window in-memory rate limiter.

Suitable for single-process deployments and tests; swap the storage backend
for Redis in multi-process production setups.
"""
import threading
import time
from collections import defaultdict, deque

from flask import current_app, request

from .errors import RateLimitError


class SlidingWindowLimiter:
    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int):
        """Record a hit; raise RateLimitError when the limit is exceeded."""
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, int(hits[0] + window_seconds - now) + 1)
                raise RateLimitError(
                    "Rate limit exceeded.",
                    details={"retry_after": retry_after, "limit": limit,
                             "window_seconds": window_seconds},
                )
            hits.append(now)
            return limit - len(hits)

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def init_app(app):
    @app.before_request
    def _rate_limit():
        if not app.config.get("RATE_LIMIT_ENABLED", True):
            return
        window = app.config["RATE_LIMIT_WINDOW_SECONDS"]
        is_auth = request.path.startswith("/api/") and "/auth/" in request.path
        limit = (app.config["RATE_LIMIT_AUTH_REQUESTS"] if is_auth
                 else app.config["RATE_LIMIT_REQUESTS"])
        bucket = "auth" if is_auth else "general"
        key = f"{bucket}:{request.remote_addr or 'unknown'}"
        remaining = limiter.check(key, limit, window)
        request.environ["ratelimit.remaining"] = remaining
        request.environ["ratelimit.limit"] = limit

    @app.after_request
    def _rate_limit_headers(resp):
        if "ratelimit.limit" in request.environ:
            resp.headers["X-RateLimit-Limit"] = str(request.environ["ratelimit.limit"])
            resp.headers["X-RateLimit-Remaining"] = str(
                request.environ["ratelimit.remaining"])
        return resp
