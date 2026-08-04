import os
import pytest
import app


@pytest.fixture
def client():
    os.environ.pop("FLASK_ENV", None)
    app.app.config["TESTING"] = True
    app.app.config["DATABASE"] = ":memory:"
    with app.app.test_client() as client:
        with app.app.app_context():
            app.init_db()
        yield client
    if os.path.exists(app.DATABASE):
        os.remove(app.DATABASE)


@pytest.fixture(autouse=True)
def cleanup_db():
    yield
    if os.path.exists(app.DATABASE):
        os.remove(app.DATABASE)


def test_shorten_requires_url(client):
    resp = client.post("/api/shorten", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "url is required"


def test_shorten_creates_code(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert "code" in data
    assert len(data["code"]) == 6
    assert data["url"] == "https://example.com"
    assert data["short_url"] == f"/{data['code']}"


def test_shorten_unique_codes(client):
    codes = set()
    for _ in range(100):
        resp = client.post("/api/shorten", json={"url": f"https://example.com/{_}"})
        assert resp.status_code == 201
        code = resp.get_json()["code"]
        assert code not in codes
        codes.add(code)


def test_redirect(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["code"]
    redirect_resp = client.get(f"/{code}")
    assert redirect_resp.status_code == 301
    assert redirect_resp.headers["Location"] == "https://example.com"


def test_redirect_not_found(client):
    resp = client.get("/notreal")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not found"


def test_get_url_info(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["code"]
    resp = client.get(f"/api/{code}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["code"] == code
    assert data["url"] == "https://example.com"
    assert "created_at" in data


def test_get_url_not_found(client):
    resp = client.get("/api/notreal")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not found"


def test_list_urls(client):
    client.post("/api/shorten", json={"url": "https://a.com"})
    client.post("/api/shorten", json={"url": "https://b.com"})
    resp = client.get("/api/urls")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
