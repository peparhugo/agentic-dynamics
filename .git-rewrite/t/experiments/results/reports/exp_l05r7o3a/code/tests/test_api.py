import pytest
import os, sys
# Ensure the repo root is on PYTHONPATH so tests can import app
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from app import create_app

def get_token(client):
    resp = client.post('/api/v1/auth/login', json={'username': 'tester', 'password': 'secret'})
    assert resp.status_code == 200
    data = resp.get_json()
    return data['access_token']

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_login_returns_token(client):
    resp = client.post('/api/v1/auth/login', json={'username': 'alice', 'password': 'password'})
    assert resp.status_code == 200
    assert 'access_token' in resp.get_json()

def test_protected_endpoint_requires_auth(client):
    resp = client.get('/api/v1/items')
    assert resp.status_code == 401

def test_list_items_pagination(client):
    token = get_token(client)
    headers = {'Authorization': f'Bearer {token}'}
    resp = client.get('/api/v1/items?page=1&per_page=3', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data
    assert len(data['items']) == 3
    assert data['page'] == 1
    assert data['per_page'] == 3
    assert 'total' in data

def test_create_item_validation(client):
    token = get_token(client)
    headers = {'Authorization': f'Bearer {token}'}
    resp = client.post('/api/v1/items', json={}, headers=headers)
    assert resp.status_code == 400 or resp.status_code == 422

def test_create_item_success(client):
    token = get_token(client)
    headers = {'Authorization': f'Bearer {token}'}
    payload = {'name': 'Golf', 'value': 70}
    resp = client.post('/api/v1/items', json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['name'] == payload['name']
    assert data['value'] == payload['value']
    assert 'id' in data

def test_api_versioning_v2(client):
    token = get_token(client)
    headers = {'Authorization': f'Bearer {token}'}
    resp = client.get('/api/v2/items', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'version' in data and data['version'] == 2
    assert 'items' in data
