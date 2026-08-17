from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config


db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from task_manager.auth import auth_bp
    from task_manager.categories import categories_bp
    from task_manager.tasks import tasks_bp
    from task_manager.users import users_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(users_bp, url_prefix="/api/users")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="Resource not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="Method not allowed"), 405

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify(error=reason), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify(error=reason), 401

    @jwt.expired_token_loader
    def expired_token(_header, _payload):
        return jsonify(error="Token has expired"), 401

    return app
