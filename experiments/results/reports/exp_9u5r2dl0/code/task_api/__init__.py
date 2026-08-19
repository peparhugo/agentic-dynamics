import os

from flask import Flask, jsonify

from .db import close_db, migrate


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "tasks.sqlite")),
        JWT_SECRET=os.environ.get("JWT_SECRET", "development-only-secret"),
        JWT_TTL_SECONDS=int(os.environ.get("JWT_TTL_SECONDS", "3600")),
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)
    app.teardown_appcontext(close_db)

    from .auth import auth_bp
    from .categories import categories_bp
    from .tasks import tasks_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="method not allowed"), 405

    with app.app_context():
        migrate()

    return app
