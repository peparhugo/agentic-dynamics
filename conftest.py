import os
import tempfile
import pytest
from app import app, init_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE"] = db_path

    init_db()

    with app.test_client() as client:
        yield client

    os.unlink(db_path)
    os.environ.pop("DATABASE", None)
