import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL DEFAULT (datetime('now')),
    actor_id INTEGER,
    action TEXT NOT NULL,
    resource TEXT,
    detail TEXT,
    ip TEXT
);
"""


def get_db():
    if "db" not in g:
        database = current_app.config["DATABASE"]
        if database == ":memory:":
            # Share one in-memory DB across connections (needed for tests).
            if "_memory_db" not in current_app.extensions:
                conn = sqlite3.connect(
                    "file:apimem?mode=memory&cache=shared",
                    uri=True,
                    check_same_thread=False,
                )
                current_app.extensions["_memory_db"] = conn
            g.db = current_app.extensions["_memory_db"]
        else:
            g.db = sqlite3.connect(database)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None and current_app.config["DATABASE"] != ":memory:":
        db.close()


def init_db(app):
    with app.app_context():
        get_db().executescript(SCHEMA)
        get_db().commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    init_db(app)
