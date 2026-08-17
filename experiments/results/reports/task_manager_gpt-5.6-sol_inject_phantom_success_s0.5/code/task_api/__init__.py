import os

from flask import Flask, jsonify

from . import auth, categories, db, tasks


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "tasks.sqlite"),
        JWT_SECRET=os.environ.get("JWT_SECRET", "development-only-secret"),
        JWT_TTL_SECONDS=3600,
        MAX_PAGE_SIZE=100,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(categories.bp)
    app.register_blueprint(tasks.bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="not_found", message="Resource not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="method_not_allowed", message="Method not allowed"), 405

    @app.errorhandler(500)
    def internal_error(_error):
        return jsonify(error="internal_error", message="An unexpected error occurred"), 500

    with app.app_context():
        db.migrate()

    return app
