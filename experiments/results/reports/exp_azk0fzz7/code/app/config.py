import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "100 per minute")
    LOG_DIR = os.environ.get("LOG_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs")))


class TestConfig(Config):
    TESTING = True
    RATELIMIT_DEFAULT = "100 per minute"  # generous, per-test app resets state
