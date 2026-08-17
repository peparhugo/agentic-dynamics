from flask import Flask, jsonify

from .config import Config
from .extensions import bcrypt, db, jwt, migrate


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from .auth import auth_bp
    from .categories import categories_bp
    from .tasks import tasks_bp
    from .users import users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(users_bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app
