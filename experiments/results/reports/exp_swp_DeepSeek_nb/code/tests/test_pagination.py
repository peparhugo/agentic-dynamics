import pytest

from app import create_app
from app.config import TestConfig
from app.models import Item, User


def _create_items(client, headers, count):
    for i in range(count):
        client.post("/v1/items", json={"name": f"Item {i}"}, headers=headers)


def test_default_page_size(client, auth_headers):
    _create_items(client, auth_headers, 25)
    resp = client.get("/v1/items", headers=auth_headers)
    data = resp.get_json()
    assert len(data["items"]) == 20
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 20
    assert data["pagination"]["total"] == 25
    assert data["pagination"]["pages"] == 2
    assert data["pagination"]["has_next"] is True
    assert data["pagination"]["has_prev"] is False


def test_pagination_second_page(client, auth_headers):
    _create_items(client, auth_headers, 25)
    resp = client.get("/v1/items?page=2", headers=auth_headers)
    data = resp.get_json()
    assert len(data["items"]) == 5
    assert data["pagination"]["has_next"] is False
    assert data["pagination"]["has_prev"] is True


def test_per_page_custom(client, auth_headers):
    _create_items(client, auth_headers, 10)
    resp = client.get("/v1/items?per_page=5", headers=auth_headers)
    data = resp.get_json()
    assert len(data["items"]) == 5
    assert data["pagination"]["per_page"] == 5


def test_per_page_capped_at_max(client, auth_headers):
    _create_items(client, auth_headers, 150)
    resp = client.get("/v1/items?per_page=500", headers=auth_headers)
    data = resp.get_json()
    assert data["pagination"]["per_page"] == 100
    assert len(data["items"]) == 100


def test_page_out_of_range_returns_empty(client, auth_headers):
    _create_items(client, auth_headers, 3)
    resp = client.get("/v1/items?page=99", headers=auth_headers)
    data = resp.get_json()
    assert data["items"] == []
    assert data["pagination"]["total"] == 3


def test_invalid_page_param(client, auth_headers):
    resp = client.get("/v1/items?page=abc", headers=auth_headers)
    assert resp.status_code == 422


def test_invalid_per_page_param(client, auth_headers):
    resp = client.get("/v1/items?per_page=xyz", headers=auth_headers)
    assert resp.status_code == 422


def test_negative_page_param(client, auth_headers):
    resp = client.get("/v1/items?page=-1", headers=auth_headers)
    assert resp.status_code == 422
