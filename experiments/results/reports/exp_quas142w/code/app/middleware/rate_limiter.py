from flask import current_app
from app.extensions import limiter


def init_limiter(app):
    limiter.init_app(app)


def rate_limit(limit_value=None):
    def decorator(f):
        limit = limit_value or current_app.config.get("RATELIMIT_DEFAULT", "100 per minute")
        return limiter.limit(limit)(f)

    return decorator
