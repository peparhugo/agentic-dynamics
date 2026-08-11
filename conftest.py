import os
import tempfile
import pytest
from app import app, init_db


@pytest.fixture(autouse=True)
def _mock_notification_task():
    import tasks
    original_delay = tasks.send_notification_email.delay
    tasks.send_notification_email.delay = lambda *a, **kw: None
    yield
    tasks.send_notification_email.delay = original_delay


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


@pytest.fixture
def auth_headers(client):
    client.post(
        "/auth/register",
        data='{"username":"testuser","password":"testpass"}',
        content_type="application/json",
    )
    resp = client.post(
        "/auth/login",
        data='{"username":"testuser","password":"testpass"}',
        content_type="application/json",
    )
    token = resp.get_json()["token"]
    return {"Authorization": "Bearer " + token}
