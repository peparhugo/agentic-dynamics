from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import Config
from app.middleware.error_handler import register_error_handlers
from app.middleware.audit import setup_audit_logging


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[app.config["RATE_LIMIT"]],
        storage_uri="memory://",
    )

    register_error_handlers(app)
    setup_audit_logging(app)

    from app.api.v1.auth import auth_bp as auth_v1
    from app.api.v1.users import users_bp as users_v1
    from app.api.v2.routes import auth_bp as auth_v2, users_bp as users_v2

    app.register_blueprint(auth_v1)
    app.register_blueprint(users_v1)
    app.register_blueprint(auth_v2)
    app.register_blueprint(users_v2)

    return app
