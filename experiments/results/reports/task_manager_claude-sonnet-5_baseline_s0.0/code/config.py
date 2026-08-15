import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRES_MINUTES = int(os.environ.get("JWT_EXPIRES_MINUTES", "60"))
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", os.path.join(BASE_DIR, "instance", "tasks.db")
    )
    TESTING = False


class TestConfig(Config):
    TESTING = True
    DATABASE_PATH = ":memory:"
    JWT_EXPIRES_MINUTES = 60
