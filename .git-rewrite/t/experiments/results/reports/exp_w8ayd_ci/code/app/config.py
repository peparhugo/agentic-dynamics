import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    JWT_SECRET = os.environ.get("JWT_SECRET", "jwt-secret-change-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24

    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per hour")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_STRATEGY = "fixed-window"

    AUDIT_LOG_FILE = os.environ.get("AUDIT_LOG_FILE", "audit.log")

    ITEMS_PER_PAGE = 20
    MAX_ITEMS_PER_PAGE = 100


class TestConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = False
    JWT_EXPIRATION_HOURS = 1
