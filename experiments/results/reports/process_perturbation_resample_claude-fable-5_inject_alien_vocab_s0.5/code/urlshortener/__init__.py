import os

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .models import db

limiter = Limiter(key_func=get_remote_address)


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", "sqlite:///urlshortener.db"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SHORT_CODE_LENGTH=7,
        BASE_URL=os.environ.get("BASE_URL", "http://localhost:5000"),
        RATELIMIT_STORAGE_URI="memory://",
        RATELIMIT_DEFAULT="200 per day;50 per hour",
        RATELIMIT_ENABLED=True,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    limiter.init_app(app)

    from .routes import bp

    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()

    return app
