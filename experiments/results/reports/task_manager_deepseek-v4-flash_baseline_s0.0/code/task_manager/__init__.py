from flask import Flask, jsonify

from .auth import auth_bp
from .categories import categories_bp
from .config import config_by_name
from .extensions import db, migrate
from .tasks import tasks_bp


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    migrate.init_app(app, db)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="Resource not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        return jsonify(error="Internal server error"), 500

    return app
