import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    JWT_SECRET = os.environ.get("JWT_SECRET", "jwt-dev-secret")
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_STRATEGY = "fixed-window"
    AUDIT_LOG_FILE = os.environ.get("AUDIT_LOG_FILE", "audit.log")


class TestConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = False
    AUDIT_LOG_FILE = "/dev/null"
