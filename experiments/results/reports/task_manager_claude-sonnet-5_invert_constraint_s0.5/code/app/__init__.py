from flask import Flask, jsonify

from config import config_by_name


def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    from app.extensions import db, jwt, migrate

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from app.errors import register_error_handlers

    register_error_handlers(app)

    from app.auth.routes import auth_bp
    from app.categories.routes import categories_bp
    from app.tasks.routes import tasks_bp
    from app.users.routes import users_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(users_bp, url_prefix="/api/users")

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @jwt.unauthorized_loader
    def unauthorized_callback(reason):
        return jsonify({"error": "Missing or invalid authorization token", "detail": reason}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({"error": "Invalid token", "detail": reason}), 422

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired"}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has been revoked"}), 401

    return app
