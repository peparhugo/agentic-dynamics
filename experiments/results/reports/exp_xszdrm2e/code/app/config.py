import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-dev-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = 3600
    JWT_REFRESH_TOKEN_EXPIRES = 86400
    RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", "memory://")
    RATELIMIT_STRATEGY = "fixed-window"
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    AUDIT_LOG_FILE = os.getenv("AUDIT_LOG_FILE", "audit.log")


class TestConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = False
    JWT_SECRET_KEY = "test-jwt-secret"
    SECRET_KEY = "test-secret"
