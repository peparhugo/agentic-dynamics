from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)


def create_app(config=None):
    app = Flask(__name__)

    if config is None:
        from app.config import Config

        config = Config

    app.config.from_object(config)

    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    from app.audit import configure_audit

    configure_audit(app)

    from app.routes.v1.auth import bp as auth_bp
    from app.routes.v1.items import bp as items_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(items_bp, url_prefix="/api/v1")

    with app.app_context():
        from app.models import Item, User  # noqa: F401

        db.create_all()

    from app.errors import register_error_handlers

    register_error_handlers(app)

    return app
