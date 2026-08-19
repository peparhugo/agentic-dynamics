from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    code TEXT PRIMARY KEY,
    target_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    click_count INTEGER NOT NULL DEFAULT 0,
    last_clicked_at TEXT
);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    clicked_at TEXT NOT NULL,
    ip_address TEXT,
    referrer TEXT,
    user_agent TEXT,
    FOREIGN KEY (code) REFERENCES urls(code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS clicks_code_clicked_at
ON clicks(code, clicked_at DESC);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database = current_app.config["DATABASE"]
        if database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    get_db().executescript(SCHEMA)
    get_db().commit()
