"""
SQLite connection management and schema setup for the Task Management API.

This module owns the *only* direct SQLite access in the application that
isn't inside a repository: acquiring/releasing the request-scoped
connection, and creating/migrating the schema on startup. Everything else
(actual queries) lives in ``repositories/``.
"""

import sqlite3

from flask import current_app, g


def get_db():
    """Return a request-scoped SQLite connection, creating it if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(database_path: str) -> None:
    """Create tables if needed and migrate older schemas in place.

    This is safe to run against a pre-existing database created before the
    ``users`` table / ``tasks.owner_id`` column existed: it only adds what's
    missing and never drops or rewrites existing rows.
    """
    conn = sqlite3.connect(database_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER"
            ")"
        )

        # ── Migration: add owner_id to tasks tables created before auth ──
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")

        # ── Migration: add email to users tables created before notifications ──
        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "email" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")

        conn.commit()
    finally:
        conn.close()
