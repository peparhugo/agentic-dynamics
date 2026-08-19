"""Flask application factory."""

import os

from flask import Flask

from .config import Config
from .db import Database
from .rate_limit import RateLimiter


def create_app(config_object=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_object is not None:
        app.config.from_object(config_object)

    # Allow environment overrides for operational settings.
    if os.environ.get("SHORTENER_DATABASE"):
        app.config["DATABASE"] = os.environ["SHORTENER_DATABASE"]
    if os.environ.get("SHORTENER_RATE_LIMIT_MAX"):
        app.config["RATE_LIMIT_MAX"] = int(os.environ["SHORTENER_RATE_LIMIT_MAX"])
    if os.environ.get("SHORTENER_RATE_LIMIT_WINDOW"):
        app.config["RATE_LIMIT_WINDOW"] = int(os.environ["SHORTENER_RATE_LIMIT_WINDOW"])

    app.extensions["db"] = Database(app.config["DATABASE"])
    app.extensions["rate_limiter"] = RateLimiter(
        app.config["RATE_LIMIT_MAX"], app.config["RATE_LIMIT_WINDOW"]
    )

    from .routes import bp
    app.register_blueprint(bp)

    return app


if __name__ == "__main__":
    create_app().run()
