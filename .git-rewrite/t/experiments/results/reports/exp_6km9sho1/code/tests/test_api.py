import os
import pytest

from app import create_app


@pytest.fixture
def app():
    app = create_app({
        'SECRET_KEY': 'dev',
        'JWT_SECRET_KEY': 'jwt-dev',
    })
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_public_endpoint(client):
    resp = client.get('/api/v1/public')
    assert resp.status_code == 200


def test_login_and_access_protected(client):
    # Login to obtain token
    resp = client.post('/api/v1/auth/login', json={"username": "admin", "password": "secret"})
    assert resp.status_code == 200
    token = resp.get_json().get('access_token')
    assert token

    # Access protected endpoint with token
    resp = client.get('/api/v1/items', headers={"Authorization": f"Bearer {token}"}, query_string={"page": 1, "per_page": 5})
    assert resp.status_code == 200
