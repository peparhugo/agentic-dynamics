"""Application configuration."""


class Config:
    """Base configuration.

    Values may be overridden via subclassing or the ``SHORTENER_*``
    environment variables when calling :func:`shortener.create_app`.
    """

    DATABASE = "shortener.db"
    # Length of generated short codes.
    SHORT_CODE_LENGTH = 6
    # Rate limiting: max requests allowed per window (per client IP).
    RATE_LIMIT_MAX = 100
    RATE_LIMIT_WINDOW = 60  # seconds
    # Maximum number of URL validation attempts before giving up.
    MAX_CODE_ATTEMPTS = 10
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    RATE_LIMIT_MAX = 5
    RATE_LIMIT_WINDOW = 60
