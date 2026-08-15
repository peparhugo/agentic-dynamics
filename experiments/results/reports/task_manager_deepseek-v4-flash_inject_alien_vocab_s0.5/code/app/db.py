import os
import sqlite3

from flask import current_app, g

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

VALID_STATUSES = {"pending", "in_progress", "completed"}
VALID_PRIORITIES = {"low", "medium", "high"}
PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def run_migrations(app):
    with app.app_context():
        db = get_db()
        db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        db.commit()
        applied = {
            row["version"]
            for row in db.execute("SELECT version FROM schema_migrations").fetchall()
        }
        files = sorted(
            f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")
        )
        for filename in files:
            version = filename.split("_", 1)[0]
            if version in applied:
                continue
            with open(os.path.join(MIGRATIONS_DIR, filename)) as fh:
                db.executescript(fh.read())
            db.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
            )
            db.commit()
        close_db()
