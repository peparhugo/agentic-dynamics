from flask import Flask

from .config import Config
from .errors import register_error_handlers
from .extensions import db
from .rate_limit import RateLimiter
from . import models


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    app.rate_limiter = RateLimiter(
        max_attempts=app.config.get("RATE_LIMIT_MAX_ATTEMPTS", 5),
        window_seconds=app.config.get("RATE_LIMIT_WINDOW_SECONDS", 60),
    )

    from .auth import auth_bp
    from .items import items_bp
    from .users import users_bp

    app.register_blueprint(auth_bp, url_prefix="/v1/auth")
    app.register_blueprint(users_bp, url_prefix="/v1/users")
    app.register_blueprint(items_bp, url_prefix="/v1/items")

    register_error_handlers(app)

    return app
