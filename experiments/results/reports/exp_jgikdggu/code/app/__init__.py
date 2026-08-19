from flask import Flask, jsonify

from .config import Config
from .extensions import db, jwt


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    jwt.init_app(app)

    from .auth import auth_bp
    from .categories import categories_bp
    from .tasks import tasks_bp
    from .users import users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(users_bp)

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return jsonify({"message": "Missing or invalid authorization header."}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({"message": "Invalid token."}), 422

    @jwt.expired_token_loader
    def expired_token_callback(header, payload):
        return jsonify({"message": "Token has expired."}), 401

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"message": "Not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"message": "Method not allowed."}), 405

    return app
