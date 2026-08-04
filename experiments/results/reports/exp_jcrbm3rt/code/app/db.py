"""SQLite access layer (stdlib only, no ORM)."""
import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id);
"""


def get_db() -> sqlite3.Connection:
    """Return a per-request connection (per-app for :memory:)."""
    database = current_app.config["DATABASE"]
    if database == ":memory:":
        # A new :memory: connection would be a brand-new empty DB, so keep a
        # single shared connection on the app for tests.
        conn = getattr(current_app, "_memory_db", None)
        if conn is None:
            conn = _connect(database)
            conn.executescript(SCHEMA)
            current_app._memory_db = conn
        return conn

    if "db" not in g:
        g.db = _connect(database)
    return g.db


def _connect(database: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    if app.config["DATABASE"] != ":memory:":
        conn = _connect(app.config["DATABASE"])
        conn.executescript(SCHEMA)
        conn.close()
    app.teardown_appcontext(close_db)
