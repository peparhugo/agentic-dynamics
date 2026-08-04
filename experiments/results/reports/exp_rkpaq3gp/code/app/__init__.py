from flask import Flask
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy

from app.config import Config

db = SQLAlchemy()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    from app.auth.routes import auth_bp
    from app.api.v1.routes import api_v1_bp
    from app.api.v2.routes import api_v2_bp
    from app.middleware.error_handler import errors_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")
    app.register_blueprint(api_v2_bp, url_prefix="/api/v2")
    app.register_blueprint(errors_bp)

    with app.app_context():
        db.create_all()

    return app
