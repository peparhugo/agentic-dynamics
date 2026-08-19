import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE = os.environ.get("DATABASE")
    JWT_EXPIRATION_HOURS = 24
    PAGINATION_DEFAULT_PER_PAGE = 10
    PAGINATION_MAX_PER_PAGE = 100
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    DATABASE = ":memory:"
    SECRET_KEY = "test-secret"
