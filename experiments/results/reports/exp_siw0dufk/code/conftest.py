import os
import sqlite3
import tempfile
import pytest

from app import create_app, init_db


@pytest.fixture
def app(tmp_path):
    db_file = tmp_path / 'test.db'
    # ensure file exists
    open(db_file, 'a').close()
    config = {
        'TESTING': True,
        'DATABASE': str(db_file),
        'RATE_LIMIT': 3,
        'BASE_URL': 'http://testserver',
        'SHORTCODE_LENGTH': 6,
    }
    app = create_app(config)

    # initialize the database
    conn = sqlite3.connect(str(db_file))
    init_db(conn)
    conn.close()

    yield app


@pytest.fixture
def client(app):
    return app.test_client()
