import sqlite3

from flask import current_app, g

MIGRATIONS = [
    {
        "version": 1,
        "name": "initial_schema",
        "sql": [
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """,
            """
            CREATE TABLE priorities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                level INTEGER NOT NULL UNIQUE
            )
            """,
            """
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """,
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                priority_id INTEGER REFERENCES priorities(id),
                category_id INTEGER REFERENCES categories(id),
                due_date TEXT,
                creator_id INTEGER NOT NULL REFERENCES users(id),
                assignee_id INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """,
            "CREATE INDEX idx_tasks_status ON tasks(status)",
            "CREATE INDEX idx_tasks_priority ON tasks(priority_id)",
            "CREATE INDEX idx_tasks_category ON tasks(category_id)",
            "CREATE INDEX idx_tasks_creator ON tasks(creator_id)",
            "CREATE INDEX idx_tasks_assignee ON tasks(assignee_id)",
            "CREATE INDEX idx_tasks_due_date ON tasks(due_date)",
            "CREATE INDEX idx_tasks_title ON tasks(title)",
        ],
    },
]

SEED_PRIORITIES = [
    {"name": "low", "level": 1},
    {"name": "medium", "level": 2},
    {"name": "high", "level": 3},
    {"name": "urgent", "level": 4},
]

SEED_CATEGORIES = ["Work", "Personal"]


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path):
    conn = _connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL "
            "DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
        )
        applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}

        for migration in MIGRATIONS:
            if migration["version"] in applied:
                continue
            conn.executescript(";\n".join(migration["sql"]))
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (migration["version"], migration["name"]),
            )
            conn.commit()

        _seed(conn)
    finally:
        conn.close()


def _seed(conn):
    count = conn.execute("SELECT COUNT(*) AS c FROM priorities").fetchone()["c"]
    if count == 0:
        conn.executemany(
            "INSERT INTO priorities (name, level) VALUES (:name, :level)", SEED_PRIORITIES
        )
    count = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
    if count == 0:
        conn.executemany("INSERT INTO categories (name) VALUES (?)", [(n,) for n in SEED_CATEGORIES])
    conn.commit()


def get_db():
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
