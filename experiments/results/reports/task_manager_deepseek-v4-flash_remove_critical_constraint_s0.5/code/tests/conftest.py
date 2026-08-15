import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from task_api import create_app  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {"TESTING": True, "DATABASE": str(tmp_path / "test_tasks.db")}
    )
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_path(app):
    return app.config["DATABASE"]
