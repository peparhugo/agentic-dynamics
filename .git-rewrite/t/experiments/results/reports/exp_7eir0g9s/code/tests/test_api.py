import os
import pytest
from app.main import create_app
from app.auth import create_token


@pytest.fixture
def client(tmp_path, monkeypatch):
    # ensure audit log writes to tmp
    os.environ['JWT_SECRET'] = 'test-secret'
    app = create_app()
    app.config['TESTING'] = True
    # clear items
    app.items = []
    with app.test_client() as c:
        yield c


def test_token_and_create_item(client):
    # request token
    r = client.post('/api/v1/token', json={'sub': 'alice'})
    assert r.status_code == 201
    token = r.get_json()['access_token']

    # create item
    r = client.post('/api/v1/items', json={'name': 'Widget'}, headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 201
    data = r.get_json()
    assert data['name'] == 'Widget'
    assert data['created_by'] == 'alice'


def test_validation(client):
    r = client.post('/api/v1/items', json={'name': ''})
    # missing auth and invalid payload -> 401 has priority for missing auth
    assert r.status_code == 401


def test_pagination(client):
    # populate items directly
    app = client.application
    for i in range(25):
        app.items.append({'id': i + 1, 'name': f'it{i+1}'})

    r = client.get('/api/v1/items?page=2&per_page=10')
    assert r.status_code == 200
    j = r.get_json()
    assert j['page'] == 2
    assert len(j['data']) == 10
