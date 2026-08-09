from flask import Flask, jsonify
from database import init_db
from auth import auth_bp
from tasks import tasks_bp


def create_app() -> Flask:
    app = Flask(__name__)

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)

    @app.route("/")
    def index():
        return jsonify({"service": "Task Management API", "version": "1.0.0"})

    return app


if __name__ == "__main__":
    init_db()
    app = create_app()
    app.run(debug=True, port=5000)
