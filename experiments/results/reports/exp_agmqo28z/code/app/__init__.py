from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(config_object="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    from app.errors import register_error_handlers
    register_error_handlers(app)

    from app.routes_v1 import register_v1_routes
    register_v1_routes(app)

    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

    return app
