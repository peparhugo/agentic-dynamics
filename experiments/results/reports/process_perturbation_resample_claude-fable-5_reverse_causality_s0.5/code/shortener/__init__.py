import os

from flask import Flask

from .storage import Storage
from .ratelimit import RateLimiter


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get("SHORTENER_DB", "urls.db"),
        SHORT_CODE_LENGTH=6,
        RATE_LIMIT_MAX=60,
        RATE_LIMIT_WINDOW=60,
    )
    if config:
        app.config.update(config)

    app.storage = Storage(app.config["DATABASE"])
    app.rate_limiter = RateLimiter(
        max_requests=app.config["RATE_LIMIT_MAX"],
        window_seconds=app.config["RATE_LIMIT_WINDOW"],
    )

    from .routes import bp
    app.register_blueprint(bp)

    @app.teardown_appcontext
    def _close(_exc):
        pass

    return app
