from flask import Flask

from app.extensions import limiter
from app.middleware.error_handler import register_error_handlers
from app.middleware.logging import register_request_logging


def create_app(config_object="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    limiter.init_app(app)

    register_error_handlers(app)
    register_request_logging(app)

    from app.api.v1 import bp as api_v1_bp

    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")

    return app
