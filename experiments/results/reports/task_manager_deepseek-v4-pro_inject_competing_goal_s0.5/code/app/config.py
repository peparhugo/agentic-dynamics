import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///tasks.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_SECONDS = int(os.environ.get("JWT_EXPIRATION_SECONDS", "3600"))

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
