import time
from functools import wraps

from flask import current_app, jsonify, request

from .db import get_db


class RateLimitExceeded(Exception):
    pass


def check_and_record(bucket_key, max_requests, window_seconds, db=None, now=None):
    """Sliding-window log rate limiter backed by SQLite.

    Every request's timestamp is persisted, so limits survive process
    restarts and are shared correctly across multiple worker processes
    (unlike an in-memory dict). Old events outside the window are pruned
    on each call to keep the table small.
    """
    db = db or get_db()
    now = time.time() if now is None else now
    window_start = now - window_seconds

    db.execute(
        "DELETE FROM rate_limit_events WHERE bucket_key = ? AND ts < ?",
        (bucket_key, window_start),
    )
    row = db.execute(
        "SELECT COUNT(*) AS n FROM rate_limit_events WHERE bucket_key = ? AND ts >= ?",
        (bucket_key, window_start),
    ).fetchone()

    if row["n"] >= max_requests:
        db.commit()
        return False

    db.execute(
        "INSERT INTO rate_limit_events (bucket_key, ts) VALUES (?, ?)",
        (bucket_key, now),
    )
    db.commit()
    return True


def rate_limited(scope):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            max_requests = current_app.config["RATE_LIMIT_MAX_REQUESTS"]
            window_seconds = current_app.config["RATE_LIMIT_WINDOW_SECONDS"]
            identity = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
            bucket_key = f"{scope}:{identity}"

            allowed = check_and_record(bucket_key, max_requests, window_seconds)
            if not allowed:
                response = jsonify(
                    {"error": "rate limit exceeded", "limit": max_requests, "window_seconds": window_seconds}
                )
                response.status_code = 429
                response.headers["Retry-After"] = str(window_seconds)
                return response
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
