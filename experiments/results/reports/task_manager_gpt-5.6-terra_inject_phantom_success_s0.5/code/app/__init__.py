import os

from flask import Flask, jsonify

from .auth import auth_bp
from .database import close_db, init_db
from .routes import api_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "tasks.sqlite"),
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "development-only-secret-change-before-production"),
        JWT_EXPIRATION_SECONDS=3600,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    app.teardown_appcontext(close_db)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    with app.app_context():
        init_db()
    return app
