from flask import Flask

from .db import init_app
from .routes import api


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE="tasks.db",
        SECRET_KEY="change-this-secret-in-production",
        JWT_EXPIRATION_SECONDS=3600,
    )
    if test_config:
        app.config.update(test_config)

    init_app(app)
    app.register_blueprint(api, url_prefix="/api")
    return app
