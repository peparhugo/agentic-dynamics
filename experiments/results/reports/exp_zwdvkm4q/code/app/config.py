import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24

    RATE_LIMIT = os.environ.get("RATE_LIMIT", "200 per day;50 per hour;5 per minute")

    PAGINATION_DEFAULT_PAGE = 1
    PAGINATION_DEFAULT_PER_PAGE = 20
    PAGINATION_MAX_PER_PAGE = 100

    LOG_FILE = "audit.log"


class TestConfig(Config):
    TESTING = True
    LOG_FILE = None
    RATE_LIMIT = "1000 per minute"
