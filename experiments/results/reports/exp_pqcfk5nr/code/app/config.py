import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-dev-secret")
    JWT_ALGORITHM = "HS256"
    PROPAGATE_EXCEPTIONS = True
    JSON_SORT_KEYS = False
    # Rate limit storage in-memory for simplicity
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    # Default limit applied to all routes unless overridden
    RATELIMIT_DEFAULT = "100 per minute"
    # Audit log file
    AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", os.path.abspath("audit.log"))


class TestingConfig(BaseConfig):
    TESTING = True
    # Lower limit for tests to make them triggerable
    RATELIMIT_DEFAULT = "3 per second"
    # Isolate audit log per test run
    AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", os.path.abspath("audit_test.log"))
