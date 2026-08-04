"""Application configuration objects."""
import os
from datetime import timedelta


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.sqlite3")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_TTL = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_TTL = timedelta(days=7)
    JWT_ISSUER = "example-api"

    # Rate limiting: requests per window (seconds)
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT_LIMIT = 100
    RATELIMIT_DEFAULT_WINDOW = 60
    RATELIMIT_AUTH_LIMIT = 10          # stricter for auth endpoints
    RATELIMIT_AUTH_WINDOW = 60

    # Pagination
    PAGINATION_DEFAULT_PER_PAGE = 20
    PAGINATION_MAX_PER_PAGE = 100

    # Supported API versions
    API_VERSIONS = ("v1",)


class TestConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RATELIMIT_ENABLED = False  # individual tests re-enable with tight limits


class ProductionConfig(BaseConfig):
    @classmethod
    def validate(cls):
        if cls.SECRET_KEY == "dev-secret-change-me":
            raise RuntimeError("SECRET_KEY must be set in production")
