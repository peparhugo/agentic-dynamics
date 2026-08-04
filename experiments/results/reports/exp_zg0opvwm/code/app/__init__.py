from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(testing=False):
    app = Flask(__name__)
    app.config.from_object("config")
    if testing:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["TESTING"] = True
    db.init_app(app)

    from app.errors import register_error_handlers

    register_error_handlers(app)

    from app.v1 import bp as v1_bp

    app.register_blueprint(v1_bp, url_prefix="/v1")

    with app.app_context():
        db.create_all()

    return app
