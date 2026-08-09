from flask import Flask

from app.config import Config
from app.extensions import limiter
from app.utils.errors import register_error_handlers


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    limiter.init_app(app)

    register_error_handlers(app)

    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    from app.api.v1.resources import api_v1_bp
    app.register_blueprint(api_v1_bp)

    from app.api.v2.resources import api_v2_bp
    app.register_blueprint(api_v2_bp)

    return app
