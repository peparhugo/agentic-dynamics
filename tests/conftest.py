import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app_module.DATABASE = db_path
    app_module.init_db()
    app_module.app.config["TESTING"] = True

    with app_module.app.test_client() as test_client:
        yield test_client

    os.close(db_fd)
    os.remove(db_path)
