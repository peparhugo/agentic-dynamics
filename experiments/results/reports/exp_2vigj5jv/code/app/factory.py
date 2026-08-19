import os
import sqlite3

from flask import Flask, g

from .api import api


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-secret"),
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "tasks.sqlite")),
        JWT_EXPIRATION_HOURS=24,
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    app.get_db = get_db
    app.teardown_appcontext(close_db)
    app.register_blueprint(api, url_prefix="/api")

    @app.cli.command("init-db")
    def init_db_command():
        from .database import init_db

        init_db(app)
        print("Initialized the database.")

    with app.app_context():
        from .database import init_db

        init_db(app)
    return app
