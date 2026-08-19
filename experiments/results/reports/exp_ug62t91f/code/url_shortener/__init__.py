from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .models import db

limiter = Limiter(key_func=get_remote_address, default_limits=["1000 per minute"])


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="dev",
        SQLALCHEMY_DATABASE_URI="sqlite:///urls.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        CODE_LENGTH=6,
        CODE_MAX_ATTEMPTS=20,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    limiter.init_app(app)

    from . import routes

    app.register_blueprint(routes.bp)

    with app.app_context():
        db.create_all()

    return app
