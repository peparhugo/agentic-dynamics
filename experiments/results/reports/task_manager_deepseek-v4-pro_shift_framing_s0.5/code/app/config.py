import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "dev-secret-key-please-change-in-production"
    )
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY", "dev-jwt-secret-key-please-change-in-production"
    )
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(os.getcwd(), "app.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
