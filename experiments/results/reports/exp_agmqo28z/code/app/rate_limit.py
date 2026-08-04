import time
from threading import Lock
from functools import wraps
from flask import request, current_app
from app.errors import RateLimitError


class RateLimiter:
    def __init__(self):
        self._store = {}
        self._lock = Lock()

    def _cleanup(self):
        for key in list(self._store.keys()):
            self._store[key] = [t for t in self._store[key] if time.time() - t < self._window]

    def is_rate_limited(self, key, max_attempts, window_seconds):
        now = time.time()
        with self._lock:
            if key not in self._store:
                self._store[key] = []
            self._store[key] = [t for t in self._store[key] if now - t < window_seconds]
            if len(self._store[key]) >= max_attempts:
                return True
            self._store[key].append(now)
            return False


_limiter = RateLimiter()


def rate_limit_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        max_attempts, window = current_app.config["RATE_LIMIT_LOGIN"]
        ip = request.remote_addr or "127.0.0.1"
        key = f"login:{ip}"

        if _limiter.is_rate_limited(key, max_attempts, window):
            raise RateLimitError(
                f"Rate limit exceeded. Maximum {max_attempts} login attempts per {window} seconds."
            )

        return f(*args, **kwargs)

    return decorated
