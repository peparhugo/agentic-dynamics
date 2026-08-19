import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-dev-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(os.path.abspath(os.path.dirname(__file__)), "app.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JSON_SORT_KEYS = False
