"""Application configuration."""
import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE = os.environ.get("DATABASE", "app.db")

    # JWT
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TTL = timedelta(minutes=15)
    JWT_REFRESH_TTL = timedelta(days=7)
    JWT_ISSUER = "example-api"

    # Rate limiting: requests per window (seconds)
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT_LIMIT = 100
    RATELIMIT_DEFAULT_WINDOW = 60
    RATELIMIT_AUTH_LIMIT = 10        # stricter for auth endpoints
    RATELIMIT_AUTH_WINDOW = 60

    # Pagination
    PAGINATION_DEFAULT_PER_PAGE = 20
    PAGINATION_MAX_PER_PAGE = 100

    # Audit
    AUDIT_LOG_FILE = os.environ.get("AUDIT_LOG_FILE")  # None -> stderr only


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    DATABASE = ":memory:"
    RATELIMIT_DEFAULT_LIMIT = 1000
    RATELIMIT_AUTH_LIMIT = 1000
