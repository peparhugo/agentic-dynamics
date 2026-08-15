import os

from flask import Flask

from app.config import Config
from app.db import init_app
from app.routes import auth_bp, categories_bp, tasks_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(os.path.dirname(app.config["DATABASE"]) or ".", exist_ok=True)

    init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(categories_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    return app
