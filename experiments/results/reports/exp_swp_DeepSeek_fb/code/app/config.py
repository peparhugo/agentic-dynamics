import os


class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "dev-secret-key-change-me-to-a-long-random-value"
    )
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY", "dev-secret-key-change-me-to-a-long-random-value"
    )
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", 900))
    JWT_REFRESH_TOKEN_EXPIRES = int(
        os.environ.get("JWT_REFRESH_TOKEN_EXPIRES", 604800)
    )

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", None)

    LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "5 per minute")

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
