"""SQLite connection handling and a tiny SQL-file migration runner."""
import os
import sqlite3

from flask import current_app, g

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations")


def get_db() -> sqlite3.Connection:
    """Return a per-request SQLite connection with rows as dict-like objects."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _applied_migrations(conn: sqlite3.Connection) -> set:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version    TEXT PRIMARY KEY,
               applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
           )"""
    )
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {r[0] for r in rows}


def run_migrations(database_path: str, migrations_dir: str = MIGRATIONS_DIR):
    """Apply any pending .sql migrations, in filename order, exactly once each."""
    conn = sqlite3.connect(database_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        applied = _applied_migrations(conn)
        for fname in sorted(os.listdir(migrations_dir)):
            if not fname.endswith(".sql") or fname in applied:
                continue
            with open(os.path.join(migrations_dir, fname), encoding="utf-8") as f:
                sql = f.read()
            with conn:  # one transaction per migration
                conn.executescript(sql)
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (fname,))
        conn.commit()
    finally:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)

    @app.cli.command("migrate")
    def migrate_command():
        """Apply pending database migrations."""
        run_migrations(app.config["DATABASE"])
        print("Migrations applied.")
