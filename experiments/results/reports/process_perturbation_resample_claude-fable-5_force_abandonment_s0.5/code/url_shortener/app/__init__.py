import os

from flask import Flask

from .db import close_db, init_db


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.path.join(os.path.dirname(app.root_path), "shortener.db"),
        BASE_URL="http://localhost:5000",
        RATE_LIMIT_MAX_REQUESTS=20,
        RATE_LIMIT_WINDOW_SECONDS=60,
        CODE_LENGTH=7,
    )
    if config:
        app.config.update(config)

    with app.app_context():
        init_db()

    app.teardown_appcontext(close_db)

    from .routes import bp

    app.register_blueprint(bp)

    return app
