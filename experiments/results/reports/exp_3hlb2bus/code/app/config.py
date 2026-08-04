"""Application configuration."""
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE = os.environ.get("DATABASE", os.path.join(os.getcwd(), "taskapi.db"))
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRES_SECONDS = int(os.environ.get("JWT_EXPIRES_SECONDS", 3600))
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    JWT_EXPIRES_SECONDS = 3600
