from flask import Flask, jsonify

from app import db as db_module
from config import Config


def create_app(config_class=Config, **config_overrides):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.update(config_overrides)

    db_module.init_app(app)

    with app.app_context():
        db_module.init_db(app)

    from app.routes.auth_routes import auth_bp
    from app.routes.category_routes import category_bp
    from app.routes.task_routes import task_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(category_bp, url_prefix="/api/categories")
    app.register_blueprint(task_bp, url_prefix="/api/tasks")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "Method not allowed"}), 405

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app
