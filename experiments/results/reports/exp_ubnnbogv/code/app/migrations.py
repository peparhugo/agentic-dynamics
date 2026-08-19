import importlib.util
import os
import sqlite3
from datetime import datetime

MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))


def _migration_files():
    files = []
    for name in sorted(os.listdir(MIGRATIONS_DIR)):
        if name.startswith("_") or name.startswith("."):
            continue
        if name.endswith(".sql") or name.endswith(".py"):
            files.append(name)
    return files


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_migrations(database_path, upto=None):
    """Apply pending migrations to an SQLite database file.

    Each migration is tracked in ``schema_migrations`` so it only runs once.
    Migrations are additive and non-destructive (old/new instances can run the
    same code against the same database during a rolling deployment).
    """
    if not database_path:
        raise ValueError("database_path is required")

    parent = os.path.dirname(os.path.abspath(database_path))
    os.makedirs(parent, exist_ok=True)

    conn = sqlite3.connect(database_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}

        for name in _migration_files():
            version = name.rsplit(".", 1)[0]
            if version in applied:
                continue
            path = os.path.join(MIGRATIONS_DIR, name)
            if name.endswith(".sql"):
                with open(path, "r", encoding="utf-8") as fh:
                    conn.executescript(fh.read())
            else:
                module = _load_module(path, f"migration_{version}")
                module.migrate(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, datetime.utcnow().isoformat()),
            )
            conn.commit()
            if upto is not None and version == upto:
                break
    finally:
        conn.close()


def applied_versions(database_path):
    conn = sqlite3.connect(database_path)
    try:
        return [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    finally:
        conn.close()
