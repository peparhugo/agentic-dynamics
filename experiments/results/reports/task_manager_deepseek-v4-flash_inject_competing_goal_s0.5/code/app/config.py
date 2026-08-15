import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class DefaultConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", os.path.join(BASE_DIR, "instance", "tasks.db")
    )
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.abspath(DATABASE_PATH)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_SECONDS = int(os.environ.get("JWT_EXPIRY_SECONDS", "3600"))
    JSON_SORT_KEYS = False
    TESTING = False
