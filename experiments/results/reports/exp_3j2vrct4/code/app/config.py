"""Application configuration."""
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE = os.environ.get("DATABASE", "app.db")

    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TTL_SECONDS = int(os.environ.get("JWT_ACCESS_TTL_SECONDS", 900))
    JWT_REFRESH_TTL_SECONDS = int(os.environ.get("JWT_REFRESH_TTL_SECONDS", 86400 * 7))
    JWT_ISSUER = "example-api"

    # Rate limiting: requests per window (seconds)
    RATELIMIT_DEFAULT_LIMIT = int(os.environ.get("RATELIMIT_DEFAULT_LIMIT", 100))
    RATELIMIT_DEFAULT_WINDOW = int(os.environ.get("RATELIMIT_DEFAULT_WINDOW", 60))
    RATELIMIT_AUTH_LIMIT = int(os.environ.get("RATELIMIT_AUTH_LIMIT", 10))
    RATELIMIT_AUTH_WINDOW = int(os.environ.get("RATELIMIT_AUTH_WINDOW", 60))
    RATELIMIT_ENABLED = True

    # Pagination
    PAGINATION_DEFAULT_PER_PAGE = 20
    PAGINATION_MAX_PER_PAGE = 100


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    JWT_ACCESS_TTL_SECONDS = 300
    RATELIMIT_DEFAULT_LIMIT = 1000
    RATELIMIT_AUTH_LIMIT = 1000
