import pytest

from app import create_app


def _login(client):
    resp = client.post('/api/v1/auth/login', json={'username': 'alice', 'password': 'password'})
    assert resp.status_code == 200
    return resp.get_json()['access_token']


def test_login_and_protected_endpoint():
    app = create_app()
    client = app.test_client()
    token = _login(client)
    # Access a protected endpoint
    resp = client.get('/api/v1/items', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code in (200, 204) or resp.status_code == 200

    # Access without token should fail
    resp2 = client.get('/api/v1/items')
    assert resp2.status_code == 401


def test_create_and_list_with_pagination():
    app = create_app()
    client = app.test_client()
    token = _login(client)
    # Create 12 items
    for i in range(12):
        resp = client.post('/api/v1/items', json={'name': f'Item {i+1}', 'value': i},
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 201
    # Page 2 with per_page 5
    resp = client.get('/api/v1/items?page=2&per_page=5', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert data['page'] == 2
    assert data['per_page'] == 5
    assert data['total'] == 12
    assert len(data['items']) == 5


def test_validation_error():
    app = create_app()
    client = app.test_client()
    token = _login(client)
    resp = client.post('/api/v1/items', json={'name': ''}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 422


def test_rate_limit():
    app = create_app()
    client = app.test_client()
    token = _login(client)
    # Send 6 requests quickly; expect the 6th to be rate-limited
    last = None
    for _ in range(6):
        last = client.get('/api/v1/items', headers={'Authorization': f'Bearer {token}'})
    assert last.status_code == 429
