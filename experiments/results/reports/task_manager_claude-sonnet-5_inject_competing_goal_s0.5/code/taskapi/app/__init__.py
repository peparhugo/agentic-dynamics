from flask import Flask

from app.config import config_by_name
from app.extensions import db, jwt, migrate


def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from app.auth.routes import auth_bp
    from app.categories.routes import categories_bp
    from app.tasks.routes import tasks_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")

    register_error_handlers(app)
    register_jwt_callbacks(jwt)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


def register_error_handlers(app):
    from app.utils import error_response

    @app.errorhandler(404)
    def not_found(e):
        return error_response("Resource not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return error_response("Method not allowed", 405)

    @app.errorhandler(500)
    def server_error(e):
        return error_response("Internal server error", 500)


def register_jwt_callbacks(jwt_manager):
    from app.utils import error_response

    @jwt_manager.unauthorized_loader
    def missing_token(reason):
        return error_response(f"Missing or invalid authorization token: {reason}", 401)

    @jwt_manager.invalid_token_loader
    def invalid_token(reason):
        return error_response(f"Invalid token: {reason}", 401)

    @jwt_manager.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return error_response("Token has expired", 401)

    @jwt_manager.revoked_token_loader
    def revoked_token(jwt_header, jwt_payload):
        return error_response("Token has been revoked", 401)
