import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    DATABASE = os.path.join(BASE_DIR, "instance", "tasks.sqlite")
    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    # Overridden per-test with a temp file path; sqlite ":memory:" can't be
    # shared across the separate connections each request opens.
    DATABASE = os.path.join(BASE_DIR, "instance", "test_tasks.sqlite")


class ProductionConfig(Config):
    pass


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
