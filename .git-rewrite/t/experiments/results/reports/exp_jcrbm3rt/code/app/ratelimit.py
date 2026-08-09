"""In-memory sliding-window rate limiter.

Suitable for a single-process deployment; swap the storage for Redis in a
multi-process setup (the decorator interface stays the same).
"""
import functools
import threading
import time
from collections import defaultdict, deque

from flask import current_app, g, request

from .errors import RateLimitError

_lock = threading.Lock()
_hits: dict = defaultdict(deque)  # key -> deque[timestamps]


def reset():
    """Clear all counters (used by tests)."""
    with _lock:
        _hits.clear()


def _client_key() -> str:
    user = getattr(g, "current_user", None)
    if user:
        return f"user:{user['id']}"
    return f"ip:{request.remote_addr or 'unknown'}"


def _check(key: str, limit: int, window: int):
    """Return (allowed, remaining, retry_after)."""
    now = time.monotonic()
    with _lock:
        dq = _hits[key]
        while dq and dq[0] <= now - window:
            dq.popleft()
        if len(dq) >= limit:
            retry_after = max(1, int(dq[0] + window - now) + 1)
            return False, 0, retry_after
        dq.append(now)
        return True, limit - len(dq), 0


def rate_limit(limit=None, window=None, scope=None):
    """Decorator applying a per-client sliding-window limit.

    Each decorated endpoint gets its own bucket (or a shared `scope`).
    """

    def decorator(fn):
        bucket = scope or f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            cfg = current_app.config
            if not cfg.get("RATELIMIT_ENABLED", True):
                return fn(*args, **kwargs)

            lim = limit or cfg["RATELIMIT_DEFAULT_LIMIT"]
            win = window or cfg["RATELIMIT_DEFAULT_WINDOW"]
            key = f"{bucket}:{_client_key()}"
            allowed, remaining, retry_after = _check(key, lim, win)

            if not allowed:
                raise RateLimitError(
                    "Rate limit exceeded, slow down",
                    retry_after=retry_after,
                    details={"limit": lim, "window_seconds": win},
                )

            response = current_app.make_response(fn(*args, **kwargs))
            response.headers["X-RateLimit-Limit"] = str(lim)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Window"] = f"{win}s"
            return response

        return wrapper

    return decorator
