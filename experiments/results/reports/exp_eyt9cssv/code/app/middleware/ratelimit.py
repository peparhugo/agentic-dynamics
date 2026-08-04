import threading
import time
from collections import defaultdict

from flask import jsonify, request


class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._attempts = defaultdict(list)

    def _cleanup(self, ip):
        now = time.time()
        window = now - 60
        self._attempts[ip] = [t for t in self._attempts[ip] if t > window]

    def is_rate_limited(self, ip, max_attempts=5, window_seconds=60):
        with self._lock:
            self._cleanup(ip)
            if len(self._attempts[ip]) >= max_attempts:
                return True
            self._attempts[ip].append(time.time())
            return False


_rate_limiter = RateLimiter()


def login_rate_limit(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.remote_addr or "127.0.0.1"
        if _rate_limiter.is_rate_limited(ip):
            return jsonify({"error": "rate limit exceeded, try again later"}), 429
        return f(*args, **kwargs)

    return decorated
