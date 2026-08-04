import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES = 3600
    JWT_REFRESH_TOKEN_EXPIRES = 86400
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 60
    PAGINATION_DEFAULT_PAGE = 1
    PAGINATION_DEFAULT_PER_PAGE = 20
    PAGINATION_MAX_PER_PAGE = 100
    AUDIT_LOG_FILE = os.environ.get("AUDIT_LOG_FILE", "audit.log")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    AUDIT_LOG_FILE = "/dev/null"
