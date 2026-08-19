from __future__ import annotations

import os

from flask import Flask

from .db import close_db, init_db
from .rate_limit import FixedWindowLimiter
from .routes import bp


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("URL_SHORTENER_DATABASE", "shortener.sqlite3"),
        RATE_LIMIT=int(os.environ.get("URL_SHORTENER_RATE_LIMIT", "60")),
        RATE_LIMIT_WINDOW=int(os.environ.get("URL_SHORTENER_RATE_WINDOW", "60")),
        SHORT_CODE_LENGTH=8,
        SHORT_CODE_ATTEMPTS=10,
    )
    if test_config:
        app.config.update(test_config)

    app.extensions["url_shortener_limiter"] = FixedWindowLimiter()
    app.teardown_appcontext(close_db)
    app.register_blueprint(bp)

    with app.app_context():
        init_db()

    return app


__all__ = ["create_app"]
