"""Application configuration."""
import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    # Rate limiting: login endpoint
    LOGIN_RATE_LIMIT_MAX = 5
    LOGIN_RATE_LIMIT_WINDOW = 60  # seconds

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"
