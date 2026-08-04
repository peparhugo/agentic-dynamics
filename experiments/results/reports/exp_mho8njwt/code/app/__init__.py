from flask import Flask, jsonify

from app.config import Config
from app.extensions import db, jwt, limiter


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    from app.models.user import User
    from app.models.item import Item
    from app.models.audit_log import AuditLog
    from app.models.refresh_token import RefreshToken

    with app.app_context():
        db.create_all()

    from app.auth.routes import auth_bp
    from app.routes.users import users_bp
    from app.routes.items import items_bp

    app.register_blueprint(auth_bp, url_prefix="/v1/auth")
    app.register_blueprint(users_bp, url_prefix="/v1/users")
    app.register_blueprint(items_bp, url_prefix="/v1/items")

    register_error_handlers(app)

    return app


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad request", "message": str(error)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": "Unauthorized", "message": str(error)}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"error": "Forbidden", "message": str(error)}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found", "message": str(error)}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"error": "Method not allowed", "message": str(error)}), 405

    @app.errorhandler(409)
    def conflict(error):
        return jsonify({"error": "Conflict", "message": str(error)}), 409

    @app.errorhandler(422)
    def unprocessable_entity(error):
        return jsonify({"error": "Unprocessable entity", "message": str(error)}), 422

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please try again later.",
        }), 429

    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({"error": "Internal server error", "message": "An unexpected error occurred"}), 500
