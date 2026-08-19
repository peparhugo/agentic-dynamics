import os
from datetime import datetime, timezone

from .db import close_db, get_db

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")


def _now():
    return datetime.now(timezone.utc).isoformat()


def apply_migrations(app):
    with app.app_context():
        db = get_db()
        try:
            db.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " version TEXT PRIMARY KEY,"
                " applied_at TEXT NOT NULL)"
            )
            db.commit()

            applied = {
                row["version"]
                for row in db.execute("SELECT version FROM schema_migrations").fetchall()
            }
            filenames = sorted(
                f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")
            )
            for filename in filenames:
                if filename in applied:
                    continue
                with open(
                    os.path.join(MIGRATIONS_DIR, filename),
                    "r",
                    encoding="utf-8",
                ) as fh:
                    db.executescript(fh.read())
                db.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (filename, _now()),
                )
                db.commit()
        finally:
            close_db()
