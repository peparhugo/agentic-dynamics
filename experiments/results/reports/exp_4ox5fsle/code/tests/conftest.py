import pytest

from url_shortener import create_app


@pytest.fixture
def clock():
    state = {"now": 1_700_000_000.0}
    state["time"] = lambda: state["now"]
    return state


@pytest.fixture
def app(tmp_path, clock):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite"),
            "CODE_LENGTH": 8,
            "RATE_LIMIT": 100,
            "TIME_PROVIDER": clock["time"],
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def shortened(client):
    response = client.post("/api/shorten", json={"url": "https://example.com/page?q=1"})
    assert response.status_code == 201
    return response.get_json()
