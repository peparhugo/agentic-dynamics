import os
from flask import Flask

from .db import close_db, init_db
from .routes import api


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-secret"),
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "tasks.sqlite")),
        JWT_EXPIRATION_SECONDS=int(os.environ.get("JWT_EXPIRATION_SECONDS", "86400")),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    app.teardown_appcontext(close_db)
    app.register_blueprint(api, url_prefix="/api")
    with app.app_context():
        init_db()
    return app
