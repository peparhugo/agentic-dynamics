import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-key-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_ERROR_MESSAGE_KEY = "error"
    DATABASE = os.environ.get("TASKMANAGER_DB", os.path.join(BASE_DIR, "taskmanager.db"))
    JSON_SORT_KEYS = False


class TestingConfig(Config):
    TESTING = True
    DATABASE = os.path.join(BASE_DIR, "taskmanager_test.db")


def get_config():
    if os.environ.get("TASKMANAGER_ENV") == "testing":
        return TestingConfig
    return Config
