import os
import sqlite3

from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate():
    """Apply SQL migrations found in the configured migrations directory.

    Applied versions are tracked in the database via PRAGMA user_version.
    """
    db = sqlite3.connect(current_app.config["DATABASE"])
    try:
        db.execute("PRAGMA foreign_keys = ON")
        current = db.execute("PRAGMA user_version").fetchone()[0]
        migrations_dir = current_app.config["MIGRATIONS_DIR"]
        if not os.path.isdir(migrations_dir):
            return
        files = sorted(f for f in os.listdir(migrations_dir) if f.endswith(".sql"))
        for filename in files:
            version = int(filename.split("_")[0])
            if version > current:
                path = os.path.join(migrations_dir, filename)
                with open(path, "r", encoding="utf-8") as fh:
                    db.executescript(fh.read())
                db.execute(f"PRAGMA user_version = {version}")
                db.commit()
    finally:
        db.close()


def row_to_dict(row):
    return dict(row) if row is not None else None


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        migrate()
