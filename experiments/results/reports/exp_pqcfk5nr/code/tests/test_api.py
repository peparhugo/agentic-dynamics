import os
import json
import time

import pytest

from app import create_app
from app.config import TestingConfig


@pytest.fixture()
def app(tmp_path):
    # Isolate audit log per test run
    class Cfg(TestingConfig):
        AUDIT_LOG_PATH = os.path.join(tmp_path, "audit.log")

    _app = create_app(Cfg)
    yield _app


@pytest.fixture()
def client(app):
    return app.test_client()


def auth_header(client):
    rv = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})
    assert rv.status_code == 200, rv.text
    token = rv.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    rv = client.get("/api/health")
    assert rv.status_code == 200
    assert rv.get_json()["status"] == "ok"


def test_protected_requires_auth(client):
    rv = client.get("/api/v1/items")
    assert rv.status_code == 401


def test_crud_and_pagination(client):
    headers = auth_header(client)
    # Create a few items
    for i in range(1, 6):
        rv = client.post("/api/v1/items", headers=headers, json={"name": f"item-{i}", "description": f"d{i}"})
        assert rv.status_code == 201

    # List with default pagination
    rv = client.get("/api/v1/items", headers=headers)
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["total"] == 5
    assert len(data["items"]) == 5  # default page_size=20

    # List with small page_size
    rv = client.get("/api/v1/items?page=2&page_size=2", headers=headers)
    data = rv.get_json()
    assert [x["name"] for x in data["items"]] == ["item-3", "item-4"]

    # Get one
    rv = client.get("/api/v1/items/1", headers=headers)
    assert rv.status_code == 200
    assert rv.get_json()["name"] == "item-1"

    # Update
    rv = client.put("/api/v1/items/1", headers=headers, json={"description": "updated"})
    assert rv.status_code == 200
    assert rv.get_json()["description"] == "updated"

    # Delete
    rv = client.delete("/api/v1/items/1", headers=headers)
    assert rv.status_code == 200
    rv = client.get("/api/v1/items/1", headers=headers)
    assert rv.status_code == 404


def test_validation_errors(client):
    headers = auth_header(client)
    # Create without name
    rv = client.post("/api/v1/items", headers=headers, json={"description": "x"})
    assert rv.status_code == 400
    # Update with empty body
    rv = client.put("/api/v1/items/99", headers=headers, json={})
    # 404 should be prioritized for unknown id
    assert rv.status_code == 404


def test_rate_limiting_login(client):
    # TestingConfig has 3 per second default; login has 5/min custom, but use quick burst on default-limited endpoints
    headers = auth_header(client)
    # Hit a low-limit endpoint multiple times quickly (create: 20/min, but default is 3/s)
    statuses = []
    for _ in range(4):
        rv = client.get("/api/v1/items", headers=headers)
        statuses.append(rv.status_code)
    assert 429 in statuses


def test_audit_log_written(client, app, tmp_path):
    headers = auth_header(client)
    # Trigger a couple requests
    client.get("/api/health")
    client.get("/api/v1/items", headers=headers)
    # Ensure log exists and has content
    log_path = app.config["AUDIT_LOG_PATH"]
    with open(log_path, "r", encoding="utf-8") as f:
        data = f.read()
        assert "method=GET" in data
        assert "path=/api/health" in data or "path=/api/v1/items" in data
