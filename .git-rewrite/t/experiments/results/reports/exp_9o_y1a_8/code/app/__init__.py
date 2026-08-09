from flask import Flask, jsonify
from flask_jwt_extended import JWTManager

from app.config import Config
from app.models import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    JWTManager(app)

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error."}), 500

    from app.routes.auth_routes import auth_bp
    from app.routes.task_routes import task_bp
    from app.routes.category_routes import category_bp
    from app.routes.user_routes import user_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(task_bp, url_prefix="/api/tasks")
    app.register_blueprint(category_bp, url_prefix="/api/categories")
    app.register_blueprint(user_bp, url_prefix="/api/users")

    with app.app_context():
        db.create_all()

    return app
