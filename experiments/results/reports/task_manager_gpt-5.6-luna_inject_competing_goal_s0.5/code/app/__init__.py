import os
import sqlite3

from flask import Flask, current_app, g, jsonify

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-secret-in-production"),
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "tasks.sqlite3")),
        JWT_EXPIRES_SECONDS=3600,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify(error="bad_request", message=error.description), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify(error="not_found", message="Resource not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify(error="method_not_allowed", message="Method not allowed"), 405

    from .auth import auth_bp
    from .tasks import tasks_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")

    with app.app_context():
        init_db()

    return app


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def init_db():
    db = sqlite3.connect(current_app.config["DATABASE"])
    db.executescript(_migration_sql())
    db.commit()
    db.close()


def _migration_sql():
    return """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo', 'in_progress', 'done')),
        category TEXT NOT NULL DEFAULT 'general',
        priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
        due_date TEXT,
        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );
    CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_filters ON tasks(owner_id, status, category, priority);
    """
