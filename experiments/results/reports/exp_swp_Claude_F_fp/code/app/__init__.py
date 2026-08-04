from flask import Flask, jsonify
from .extensions import db
from .errors import register_error_handlers


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY="change-me",
        JWT_ACCESS_TTL=900,
        JWT_REFRESH_TTL=86400 * 7,
        RATE_LIMIT_LOGIN_MAX=5,
        RATE_LIMIT_LOGIN_WINDOW=60,
    )
    if config:
        app.config.update(config)

    db.init_app(app)

    from .api_v1 import bp as v1_bp
    app.register_blueprint(v1_bp, url_prefix="/v1")

    register_error_handlers(app)

    with app.app_context():
        db.create_all()

    return app
