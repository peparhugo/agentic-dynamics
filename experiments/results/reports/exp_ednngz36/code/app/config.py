"""Application configuration."""
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TTL_SECONDS = int(os.environ.get("JWT_ACCESS_TTL_SECONDS", 900))
    JWT_REFRESH_TTL_SECONDS = int(os.environ.get("JWT_REFRESH_TTL_SECONDS", 86400))

    # Rate limiting: fixed window
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", 100))
    RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", 60))
    # Stricter limit for auth endpoints (brute-force protection)
    RATE_LIMIT_AUTH_REQUESTS = int(os.environ.get("RATE_LIMIT_AUTH_REQUESTS", 10))

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    JWT_ACCESS_TTL_SECONDS = 300
    RATE_LIMIT_REQUESTS = 5
    RATE_LIMIT_AUTH_REQUESTS = 5
    RATE_LIMIT_WINDOW_SECONDS = 60
