import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.DATA_FILE = str(tmp_path / "tasks.json")
    app_module.init_store()
    app_module.app.config["TESTING"] = True
    try:
        app_module.limiter.reset()
    except Exception:
        pass
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def alice(client):
    resp = client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )
    assert resp.status_code == 201
    token = resp.get_json()["token"]
    return {"username": "alice", "token": token}


@pytest.fixture()
def auth(alice):
    return {"Authorization": f"Bearer {alice['token']}"}


@pytest.fixture()
def bob(client):
    resp = client.post(
        "/auth/register", json={"username": "bob", "password": "bobpass"}
    )
    assert resp.status_code == 201
    return {"username": "bob", "token": resp.get_json()["token"]}


@pytest.fixture()
def bob_auth(bob):
    return {"Authorization": f"Bearer {bob['token']}"}
