import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE = os.environ.get("DATABASE", "app.db")

    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TTL_SECONDS = int(os.environ.get("JWT_ACCESS_TTL_SECONDS", 900))
    JWT_REFRESH_TTL_SECONDS = int(os.environ.get("JWT_REFRESH_TTL_SECONDS", 60 * 60 * 24 * 7))

    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", 60))
    RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", 60))
    # Stricter bucket for auth endpoints (mitigates credential stuffing).
    RATE_LIMIT_AUTH_REQUESTS = int(os.environ.get("RATE_LIMIT_AUTH_REQUESTS", 10))

    PAGINATION_DEFAULT_PER_PAGE = 20
    PAGINATION_MAX_PER_PAGE = 100

    AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH")  # None -> stderr


class TestConfig(Config):
    TESTING = True
    DATABASE = ":memory:"
    SECRET_KEY = "test-secret"
    RATE_LIMIT_REQUESTS = 1000
    RATE_LIMIT_AUTH_REQUESTS = 1000
