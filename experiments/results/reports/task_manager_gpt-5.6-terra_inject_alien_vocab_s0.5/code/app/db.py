import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate():
    db = get_db()
    migrations = Path(current_app.root_path).parent / "migrations"
    db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
    applied = {row["version"] for row in db.execute("SELECT version FROM schema_migrations")}
    for path in sorted(migrations.glob("*.sql")):
        if path.name not in applied:
            db.executescript(path.read_text())
            db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (path.name,))
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        migrate()
