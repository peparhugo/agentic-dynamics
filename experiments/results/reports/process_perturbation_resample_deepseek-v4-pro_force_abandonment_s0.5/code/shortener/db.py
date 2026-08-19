import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    long_url TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    clicks INTEGER NOT NULL DEFAULT 0,
    last_click_at TEXT
);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id INTEGER NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    clicked_at TEXT NOT NULL,
    ip TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_clicks_url_id ON clicks(url_id);
CREATE INDEX IF NOT EXISTS idx_clicks_clicked_at ON clicks(clicked_at);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)
