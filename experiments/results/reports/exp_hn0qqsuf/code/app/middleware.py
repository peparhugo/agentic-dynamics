import time
import threading
from flask import request


class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._windows = {}

    def is_rate_limited(self, key, max_requests, window_seconds):
        now = time.time()
        with self._lock:
            if key not in self._windows:
                self._windows[key] = []
            window = self._windows[key]
            window[:] = [t for t in window if now - t < window_seconds]
            if len(window) >= max_requests:
                return True
            window.append(now)
            return False

    def remaining(self, key, max_requests, window_seconds):
        now = time.time()
        with self._lock:
            if key not in self._windows:
                return max_requests
            window = self._windows[key]
            window[:] = [t for t in window if now - t < window_seconds]
            return max(0, max_requests - len(window))


_rate_limiter = RateLimiter()


def rate_limit(requests_count, period_seconds, key_func=None):
    def decorator(f):
        def wrapper(*args, **kwargs):
            if key_func:
                key = key_func()
            else:
                key = request.remote_addr or "127.0.0.1"
            if _rate_limiter.is_rate_limited(key, requests_count, period_seconds):
                remaining = 0
                retry_after = period_seconds
                response = {"error": "Too many requests", "retry_after": retry_after}, 429
                return response
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator
