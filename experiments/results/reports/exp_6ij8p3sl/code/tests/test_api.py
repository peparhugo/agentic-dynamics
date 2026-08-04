import json
import pytest

from app import app, reset_store


@pytest.fixture(autouse=True)
def run_around_tests():
    # Reset in-memory store before each test
    reset_store()
    yield
    # Teardown not needed


def get_token(client):
    resp = client.post('/api/v1/auth/login', json={"username": "tester", "password": "secret"})
    data = resp.get_json()
    return data.get('access_token')


def test_login_provides_token():
    with app.test_client() as client:
        resp = client.post('/api/v1/auth/login', json={"username": "tester", "password": "secret"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'access_token' in data


def test_create_item_requires_auth():
    with app.test_client() as client:
        resp = client.post('/api/v1/items', json={"name": "item1", "value": 1})
        assert resp.status_code == 401


def test_create_item_with_auth():
    with app.test_client() as client:
        token = get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post('/api/v1/items', json={"name": "item1", "value": 10}, headers=headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "item1"
        assert data["value"] == 10
        assert data["id"] == 1


def test_list_items_pagination():
    with app.test_client() as client:
        token = get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        # Create 3 items
        client.post('/api/v1/items', json={"name": "a", "value": 1}, headers=headers)
        client.post('/api/v1/items', json={"name": "b", "value": 2}, headers=headers)
        client.post('/api/v1/items', json={"name": "c", "value": 3}, headers=headers)
        resp = client.get('/api/v1/items?page=1&per_page=2')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['page'] == 1
        assert data['per_page'] == 2
        assert 'total' in data
        assert isinstance(data['items'], list)
        assert len(data['items']) <= 2


def test_get_item():
    with app.test_client() as client:
        token = get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        client.post('/api/v1/items', json={"name": "x", "value": 5}, headers=headers)
        resp = client.get('/api/v1/items/1')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['id'] == 1


def test_validation_error_on_create():
    with app.test_client() as client:
        token = get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post('/api/v1/items', json={"name": "incomplete"}, headers=headers)
        assert resp.status_code == 422
