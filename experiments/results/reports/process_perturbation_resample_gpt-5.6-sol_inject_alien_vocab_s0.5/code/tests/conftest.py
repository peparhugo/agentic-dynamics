import pytest

from urlshortener import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite3"),
            "RATE_LIMIT": 1000,
            "IP_HASH_SALT": "test-salt",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def short_link(client):
    response = client.post(
        "/api/v1/urls", json={"url": "https://example.com/articles?id=7", "custom_code": "story"}
    )
    assert response.status_code == 201
    return response.get_json()
