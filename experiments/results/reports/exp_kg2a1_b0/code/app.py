import os
from flask import Flask
from db import init_db
from api import api


def create_app(testing=False):
    app = Flask(__name__)
    app.config["TESTING"] = testing
    db_path = os.environ.get("DB_PATH", "urls.db")
    init_db(db_path)
    app.config["DB_PATH"] = db_path
    app.register_blueprint(api)
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
