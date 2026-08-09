import pytest

from config import Config
from storage import Storage
from app import app


@pytest.fixture(autouse=True)
def override_config(monkeypatch):
    monkeypatch.setattr(Config, "DB_PATH", ":memory:")
    monkeypatch.setattr(Config, "BASE_URL", "http://localhost:5000")
    monkeypatch.setattr(Config, "RATE_LIMIT_REQUESTS", 1000)
    monkeypatch.setattr(Config, "RATE_LIMIT_WINDOW_SEC", 60)
    monkeypatch.setattr(Config, "CREATE_RATE_LIMIT_REQUESTS", 1000)
    monkeypatch.setattr(Config, "CREATE_RATE_LIMIT_WINDOW_SEC", 60)
    monkeypatch.setattr(Config, "DEFAULT_TTL_DAYS", 90)


@pytest.fixture
def client(override_config):
    import app as app_module
    app_module.storage = Storage(":memory:")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def sample_url(client):
    resp = client.post(
        "/api/shorten",
        json={"url": "https://example.com/test"},
        content_type="application/json",
    )
    return resp.get_json()["short_code"]
