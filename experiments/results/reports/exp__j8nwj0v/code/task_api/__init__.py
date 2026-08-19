import os

from flask import Flask, jsonify

from .auth import auth_bp
from .db import close_db, init_db
from .tasks import tasks_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "tasks.sqlite"),
        JWT_SECRET=os.environ.get(
            "JWT_SECRET", "development-only-change-me-32-bytes"
        ),
        JWT_TTL_SECONDS=3600,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    app.teardown_appcontext(close_db)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(tasks_bp, url_prefix="/tasks")

    with app.app_context():
        init_db()

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app
