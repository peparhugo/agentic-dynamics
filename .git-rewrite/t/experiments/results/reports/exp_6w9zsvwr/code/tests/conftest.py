import pytest

from url_shortener import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite3"),
            "RATE_LIMIT": 100,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def shortened(client):
    response = client.post("/api/urls", json={"url": "https://example.com/path?q=1"})
    assert response.status_code == 201
    return response.get_json()
