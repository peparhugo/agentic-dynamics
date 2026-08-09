from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from app.config import Config

db = SQLAlchemy()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    limiter.init_app(app)

    from app.middleware.error_handler import register_error_handlers
    register_error_handlers(app)

    from app.v1.routes import bp as v1_bp
    from app.v2.routes import bp as v2_bp
    app.register_blueprint(v1_bp, url_prefix="/api/v1")
    app.register_blueprint(v2_bp, url_prefix="/api/v2")

    with app.app_context():
        db.create_all()

    return app
