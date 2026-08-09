import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_create_short_url(client):
    rv = client.post("/shorten", json={"url": "https://example.com"})
    assert rv.status_code == 201
    data = rv.get_json()
    assert "short_id" in data
    assert len(data["short_id"]) == 6
    assert data["original"] == "https://example.com"


def test_create_missing_url(client):
    rv = client.post("/shorten", json={})
    assert rv.status_code == 400
    assert "error" in rv.get_json()


def test_redirect(client):
    rv = client.post("/shorten", json={"url": "https://example.com"})
    sid = rv.get_json()["short_id"]
    rv = client.get(f"/{sid}", follow_redirects=False)
    assert rv.status_code == 302
    assert rv.headers["Location"] == "https://example.com"


def test_redirect_not_found(client):
    rv = client.get("/nonexist")
    assert rv.status_code == 404


def test_list_urls(client):
    client.post("/shorten", json={"url": "https://example.com"})
    rv = client.get("/urls")
    assert rv.status_code == 200
    assert len(rv.get_json()) >= 1


def test_same_url_same_id(client):
    rv1 = client.post("/shorten", json={"url": "https://dupe.com"})
    rv2 = client.post("/shorten", json={"url": "https://dupe.com"})
    assert rv1.get_json()["short_id"] == rv2.get_json()["short_id"]
