import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from taskmanager import create_app


@pytest.fixture()
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app({"TESTING": True, "DATABASE": db_path})
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def _register(client, username, email, password="password123"):
    return client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )


@pytest.fixture()
def users(client):
    alice = _register(client, "alice", "alice@example.com")
    bob = _register(client, "bob", "bob@example.com")
    carol = _register(client, "carol", "carol@example.com")
    return {
        "alice": {"token": alice.get_json()["access_token"], "id": alice.get_json()["user"]["id"]},
        "bob": {"token": bob.get_json()["access_token"], "id": bob.get_json()["user"]["id"]},
        "carol": {"token": carol.get_json()["access_token"], "id": carol.get_json()["user"]["id"]},
    }


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def priority_ids(client, users):
    resp = client.get("/priorities", headers=auth_headers(users["alice"]["token"]))
    return {item["name"]: item["id"] for item in resp.get_json()["items"]}


@pytest.fixture()
def category_ids(client, users):
    resp = client.get("/categories", headers=auth_headers(users["alice"]["token"]))
    return {item["name"]: item["id"] for item in resp.get_json()["items"]}


def create_task(client, token, **overrides):
    payload = {"title": "Default task"}
    payload.update(overrides)
    return client.post("/tasks", json=payload, headers=auth_headers(token))
