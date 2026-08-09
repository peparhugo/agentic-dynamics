from flask import Flask

from config import RATE_LIMIT_DEFAULT
from middleware.rate_limiter import limiter
from middleware.error_handler import register_error_handlers
from routes.v1.users import v1
from routes.v2.users import v2


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "flask-secret-key"

    limiter.init_app(app)
    limiter._default_limits = [RATE_LIMIT_DEFAULT]

    register_error_handlers(app)

    app.register_blueprint(v1)
    app.register_blueprint(v2)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
