from flask import Flask, jsonify

from app.config import Config
from app.extensions import bcrypt, db, jwt, migrate


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from app.auth import auth_bp
    from app.categories import category_bp
    from app.tasks import task_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(task_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"message": "resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"message": "method not allowed"}), 405

    @app.errorhandler(422)
    def unprocessable(_error):
        return jsonify({"message": "unprocessable entity"}), 422

    return app
