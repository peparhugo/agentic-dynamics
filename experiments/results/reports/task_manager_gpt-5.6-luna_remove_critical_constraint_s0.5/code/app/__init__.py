"""Task management API application factory."""

from pathlib import Path

from flask import Flask

from .db import close_db, init_db
from .tasks import tasks_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "tasks.sqlite"),
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    app.register_blueprint(tasks_bp, url_prefix="/api/v1")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    with app.app_context():
        init_db()
    return app
