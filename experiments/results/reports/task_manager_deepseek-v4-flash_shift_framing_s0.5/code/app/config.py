import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    JWT_EXPIRATION_SECONDS = int(os.environ.get("JWT_EXPIRATION_SECONDS", "3600"))
    DATABASE = os.environ.get(
        "DATABASE", os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance", "taskmanager.db")
    )
    MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
