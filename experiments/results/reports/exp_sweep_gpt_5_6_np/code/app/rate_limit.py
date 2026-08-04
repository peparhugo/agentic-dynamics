from collections import defaultdict, deque
from functools import wraps
from threading import Lock
from time import monotonic

from flask import current_app, jsonify, request


class LoginRateLimiter:
    def __init__(self):
        self.attempts = defaultdict(deque)
        self.lock = Lock()

    def init_app(self, app):
        self.clear()
        app.extensions["login_rate_limiter"] = self

    def clear(self):
        with self.lock:
            self.attempts.clear()

    def limit(self, maximum=5, window=60):
        def decorator(func):
            @wraps(func)
            def wrapped(*args, **kwargs):
                if not current_app.config.get("LOGIN_RATE_LIMIT_ENABLED", True):
                    return func(*args, **kwargs)
                key = request.remote_addr or "unknown"
                now = monotonic()
                with self.lock:
                    attempts = self.attempts[key]
                    while attempts and attempts[0] <= now - window:
                        attempts.popleft()
                    if len(attempts) >= maximum:
                        retry_after = max(1, int(window - (now - attempts[0])) + 1)
                        response = jsonify(
                            error={
                                "code": "rate_limit_exceeded",
                                "message": "Too many login attempts. Try again later.",
                            }
                        )
                        response.status_code = 429
                        response.headers["Retry-After"] = str(retry_after)
                        return response
                    attempts.append(now)
                return func(*args, **kwargs)

            return wrapped

        return decorator


login_limiter = LoginRateLimiter()
