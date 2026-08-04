"""URL shortener Flask application factory."""

from __future__ import annotations

import os

from flask import Flask

from .storage import Storage
from .ratelimit import SlidingWindowLimiter


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get("SHORTENER_DB", "shortener.db"),
        RATE_LIMIT_MAX=30,          # requests
        RATE_LIMIT_WINDOW=60.0,     # seconds
        CODE_LENGTH=7,
    )
    if config:
        app.config.update(config)

    app.extensions["storage"] = Storage(app.config["DATABASE"])
    app.extensions["limiter"] = SlidingWindowLimiter(
        max_requests=app.config["RATE_LIMIT_MAX"],
        window_seconds=app.config["RATE_LIMIT_WINDOW"],
    )

    from .api import bp as api_bp
    app.register_blueprint(api_bp)

    return app
