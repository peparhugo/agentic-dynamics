import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    code TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_links_url ON links(url);

CREATE TABLE IF NOT EXISTS click_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    ts REAL NOT NULL,
    referrer TEXT,
    ip TEXT,
    FOREIGN KEY(code) REFERENCES links(code)
);

CREATE INDEX IF NOT EXISTS idx_click_events_code ON click_events(code);

CREATE TABLE IF NOT EXISTS rate_limit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bucket_key TEXT NOT NULL,
    ts REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_bucket_ts ON rate_limit_events(bucket_key, ts);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
