import os
import tempfile

fd, path = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DATABASE"] = path

import pytest

import app as app_module


@pytest.fixture()
def app():
    app_module.app.config["TESTING"] = True
    return app_module.app


@pytest.fixture(autouse=True)
def reset_db():
    with app_module.get_db() as conn:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM users")
        conn.commit()
    yield


@pytest.fixture()
def client(app):
    with app.test_client() as client:
        yield client
