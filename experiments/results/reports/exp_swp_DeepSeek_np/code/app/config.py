import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-secret-key-change-me-0123456789")
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY", "insecure-jwt-secret-key-change-me-0123456789"
    )
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", "900"))
    JWT_REFRESH_TOKEN_EXPIRES = int(
        os.environ.get("JWT_REFRESH_TOKEN_EXPIRES", "2592000")
    )

    # Rate limiting (login endpoint)
    RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "1") == "1"
    RATE_LIMIT_MAX_ATTEMPTS = int(os.environ.get("RATE_LIMIT_MAX_ATTEMPTS", "5"))
    RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-jwt-secret-key-that-is-long-enough-0123456789"
    SECRET_KEY = "test-secret-key-that-is-long-enough-0123456789"
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_MAX_ATTEMPTS = 5
    RATE_LIMIT_WINDOW = 60
