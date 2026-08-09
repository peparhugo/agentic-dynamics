"""URL shortener Flask application factory."""

from __future__ import annotations

import os

from flask import Flask

from .storage import SQLiteStorage
from .ratelimit import RateLimiter


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config.update(
        DATABASE=os.environ.get("SHORTENER_DB", "shortener.db"),
        # Rate limit: requests per window (seconds), keyed by client IP.
        RATE_LIMIT_REQUESTS=int(os.environ.get("RATE_LIMIT_REQUESTS", 10)),
        RATE_LIMIT_WINDOW=float(os.environ.get("RATE_LIMIT_WINDOW", 60)),
        CODE_LENGTH=6,
    )
    if config:
        app.config.update(config)

    app.extensions["storage"] = SQLiteStorage(app.config["DATABASE"])
    app.extensions["rate_limiter"] = RateLimiter(
        max_requests=app.config["RATE_LIMIT_REQUESTS"],
        window_seconds=app.config["RATE_LIMIT_WINDOW"],
    )

    from .api import bp as api_bp

    app.register_blueprint(api_bp)

    return app
