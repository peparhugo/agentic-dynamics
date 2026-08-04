import pytest

from app import AUDIT_LOG, ITEMS, create_app


@pytest.fixture
def client():
    original_items = list(ITEMS)
    AUDIT_LOG.clear()
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "RATE_LIMIT_REQUESTS": 3,
            "RATE_LIMIT_WINDOW_SECONDS": 60,
        }
    )
    with app.test_client() as client:
        yield client
    ITEMS[:] = original_items
    AUDIT_LOG.clear()


@pytest.fixture
def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})
    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
