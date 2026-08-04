import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    DATABASE = os.environ.get("DATABASE_PATH", os.path.join(basedir, "taskapi.db"))
    JWT_SECRET = os.environ.get("JWT_SECRET", "jwt-secret-change-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24
    PAGE_SIZE_DEFAULT = 20
    PAGE_SIZE_MAX = 100
    BCRYPT_ROUNDS = 12


class TestConfig(Config):
    TESTING = True
    DATABASE = os.path.join(basedir, "test_taskapi.db")
    BCRYPT_ROUNDS = 4
    JWT_EXPIRATION_HOURS = 1
