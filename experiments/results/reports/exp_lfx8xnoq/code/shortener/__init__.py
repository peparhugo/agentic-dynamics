import os
import tempfile

from flask import Flask

from . import db, routes

DEFAULTS = {
    "SECRET_KEY": os.environ.get("SHORTENER_SECRET", "dev-secret-change-me"),
    "DATABASE": os.environ.get(
        "SHORTENER_DB", os.path.join(tempfile.gettempdir(), "shortener.db")
    ),
    "CODE_LENGTH": 8,
    "MAX_CODE_ATTEMPTS": 64,
    "SHORTEN_LIMIT": (10, 60),
    "ANALYTICS_LIMIT": (30, 60),
    "REDIRECT_LIMIT": (1000, 60),
}


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(DEFAULTS)
    if config:
        app.config.update(config)

    from .limiter import Limiter

    app.extensions["limiter"] = Limiter()

    db.init_app(app)
    db.init_db(app)
    routes.init_app(app)

    return app
