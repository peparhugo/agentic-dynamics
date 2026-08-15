import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, g, jsonify

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-development-secret"),
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "tasks.sqlite3")),
        JWT_EXPIRES_MINUTES=int(os.environ.get("JWT_EXPIRES_MINUTES", "60")),
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    from .auth import auth_bp
    from .tasks import tasks_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api")

    @app.teardown_appcontext
    def close_db(_exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="resource not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="method not allowed"), 405

    with app.app_context():
        init_db()
    return app


def db():
    if "db" not in g:
        app = __import__("flask").current_app
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def init_db():
    database = __import__("flask").current_app.config["DATABASE"]
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        migration = os.path.join(os.path.dirname(__file__), "migrations", "001_initial.sql")
        with open(migration, encoding="utf-8") as file:
            connection.executescript(file.read())
        connection.commit()
    finally:
        connection.close()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
