from flask import Flask, jsonify

from app.extensions import db, jwt, migrate


def create_app(config_object="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from app.routes.auth import auth_bp
    from app.routes.tasks import tasks_bp
    from app.routes.categories import categories_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "method not allowed"}), 405

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({"error": "invalid token", "detail": reason}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return jsonify({"error": "missing token", "detail": reason}), 401

    return app
