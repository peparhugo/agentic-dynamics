import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'urlshortener.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SHORT_CODE_LENGTH = 6
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"
    # Rate limits (Flask-Limiter syntax)
    SHORTEN_RATE_LIMIT = "10 per minute"
    REDIRECT_RATE_LIMIT = "60 per minute"
    DEFAULT_RATE_LIMIT = "200 per hour"


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    RATELIMIT_ENABLED = False
    SHORTEN_RATE_LIMIT = "10 per minute"
    REDIRECT_RATE_LIMIT = "60 per minute"
