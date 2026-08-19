import os


def init_db(app):
    db = app.get_db()
    migration_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")
    with open(os.path.join(migration_dir, "001_initial.sql"), encoding="utf-8") as migration:
        db.executescript(migration.read())
    db.commit()
