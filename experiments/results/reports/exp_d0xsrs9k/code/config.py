import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    JWT_SECRET = os.environ.get("JWT_SECRET", "jwt-secret-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    RATE_LIMIT_DEFAULT = "100 per minute"
    RATE_LIMIT_AUTH = "5 per minute"
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    JWT_SECRET = "test-jwt-secret"
    RATE_LIMIT_DEFAULT = "1000 per minute"
    RATE_LIMIT_AUTH = "1000 per minute"
