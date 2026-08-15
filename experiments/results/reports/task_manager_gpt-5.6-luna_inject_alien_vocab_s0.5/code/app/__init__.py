import os
from pathlib import Path

from flask import Flask

from .db import close_db, init_db


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        DATABASE=os.environ.get("DATABASE", str(Path(app.instance_path) / "tasks.sqlite")),
        JWT_TTL_SECONDS=3600,
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    from .auth import bp as auth_bp
    from .tasks import bp as tasks_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp)
    return app
