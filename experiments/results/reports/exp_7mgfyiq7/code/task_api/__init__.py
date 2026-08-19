import os
from pathlib import Path

from flask import Flask, jsonify

from . import auth, categories, db, tasks


def create_app(test_config=None):
    app = Flask(__name__)
    root = Path(__file__).resolve().parent.parent
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE_PATH", str(root / "tasks.sqlite3")),
        MIGRATIONS_DIR=str(root / "migrations"),
        SECRET_KEY=os.environ.get("SECRET_KEY", "development-only-change-me"),
        JWT_EXPIRES_SECONDS=24 * 60 * 60,
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    auth.register_routes(app)
    categories.register_routes(app)
    tasks.register_routes(app)

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="Method not allowed"), 405

    return app
