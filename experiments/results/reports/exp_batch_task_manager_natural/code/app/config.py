import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-to-32-bytes-minimum!")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_EXPIRATION = timedelta(hours=int(os.environ.get("JWT_EXPIRATION_HOURS", "24")))
    JWT_ALGORITHM = "HS256"

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(os.path.dirname(os.path.dirname(__file__)), "task_manager.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEFAULT_PAGE_SIZE = 10
    MAX_PAGE_SIZE = 100


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key-that-is-at-least-32-bytes-long!!"
    JWT_SECRET_KEY = "test-secret-key-that-is-at-least-32-bytes-long!!"
