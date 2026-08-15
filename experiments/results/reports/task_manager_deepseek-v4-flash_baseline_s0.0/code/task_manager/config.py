import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///task_manager.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_EXPIRATION_DELTA = timedelta(hours=int(os.environ.get("JWT_EXPIRATION_HOURS", "12")))
    JWT_ALGORITHM = "HS256"
    DEFAULT_PER_PAGE = 10
    MAX_PER_PAGE = 100
    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"
    JWT_EXPIRATION_DELTA = timedelta(hours=12)


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": Config,
}
