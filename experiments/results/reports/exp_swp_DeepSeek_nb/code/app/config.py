import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-in-production-please")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(os.getcwd(), "app.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRES = int(os.environ.get("ACCESS_TOKEN_EXPIRES", 900))       # 15 minutes
    REFRESH_TOKEN_EXPIRES = int(os.environ.get("REFRESH_TOKEN_EXPIRES", 604800))  # 7 days

    LOGIN_RATE_LIMIT = 5          # attempts
    LOGIN_RATE_LIMIT_WINDOW = 60  # seconds

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100


class TestConfig(Config):
    TESTING = True
    PROPAGATE_EXCEPTIONS = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key-that-is-long-enough-for-hs256"
    LOGIN_RATE_LIMIT = 5
    LOGIN_RATE_LIMIT_WINDOW = 60
