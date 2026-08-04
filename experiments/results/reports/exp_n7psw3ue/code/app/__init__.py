from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(config_object=None):
    app = Flask(__name__)

    if config_object:
        app.config.from_object(config_object)
    else:
        from app.config import Config

        app.config.from_object(Config)

    db.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.items import items_bp

    app.register_blueprint(auth_bp, url_prefix="/v1/auth")
    app.register_blueprint(items_bp, url_prefix="/v1/items")

    from app.errors import register_error_handlers

    register_error_handlers(app)

    with app.app_context():
        db.create_all()

    return app
