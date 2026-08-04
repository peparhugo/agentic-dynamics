import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert rv.get_json()["message"] == "URL shortener v1"


def test_shorten_missing_url(client):
    rv = client.post("/shorten", json={})
    assert rv.status_code == 400
    assert "missing" in rv.get_json()["error"]


def test_shorten_invalid_url(client):
    rv = client.post("/shorten", json={"url": "not-a-url"})
    assert rv.status_code == 400
    assert "invalid" in rv.get_json()["error"]


def test_shorten_and_redirect(client):
    rv = client.post("/shorten", json={"url": "https://example.com"})
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["code"]
    assert "short_url" in data

    rv = client.get(f"/{data['code']}")
    assert rv.status_code == 302
    assert rv.headers["Location"] == "https://example.com"


def test_redirect_not_found(client):
    rv = client.get("/deadbeef")
    assert rv.status_code == 404
    assert rv.get_json()["error"] == "not found"
