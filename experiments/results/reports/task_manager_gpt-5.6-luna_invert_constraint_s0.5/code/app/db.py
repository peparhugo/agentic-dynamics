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


def init_db():
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
    migration_dir = Path(current_app.root_path).parent / "migrations"
    for path in sorted(migration_dir.glob("*.sql")):
        version = int(path.name.split("_", 1)[0])
        if db.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone():
            continue
        db.executescript(path.read_text(encoding="utf-8"))
        db.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
    db.commit()
