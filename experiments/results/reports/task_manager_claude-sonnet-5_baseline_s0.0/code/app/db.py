import sqlite3

from flask import current_app, g

from migrations.migrate import apply_migrations


def get_db():
    if "db" not in g:
        db_path = current_app.config["DATABASE_PATH"]
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        db = get_db()
        apply_migrations(db)


def init_app(app):
    app.teardown_appcontext(close_db)
