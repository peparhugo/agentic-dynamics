import json
from app.extensions import db
from app.models import User, Item, AuditLog


def register(client, username='alice', password='password'):
    return client.post('/v1/auth/register', json={'username': username, 'password': password})


def login(client, username='alice', password='password'):
    return client.post('/v1/auth/login', json={'username': username, 'password': password})


def test_register_and_login(client):
    r = register(client)
    assert r.status_code == 201
    r = login(client)
    assert r.status_code == 200
    data = r.get_json()
    assert 'access_token' in data and 'refresh_token' in data


def test_rate_limit_on_login(client):
    register(client, username='bob')
    # 5 failed attempts allowed, 6th should be 429
    for i in range(5):
        r = login(client, username='bob', password='wrong')
        assert r.status_code == 401
    r = login(client, username='bob', password='wrong')
    assert r.status_code == 429


def test_token_refresh_and_protected_endpoints(client):
    register(client, username='carol')
    r = login(client, username='carol')
    tokens = r.get_json()
    access = tokens['access_token']
    refresh = tokens['refresh_token']

    # create item
    r = client.post('/v1/items', json={'name': 'it1'}, headers={'Authorization': f'Bearer {access}'})
    assert r.status_code == 201
    item = r.get_json()

    # list items pagination
    # create more items
    for i in range(24):
        client.post('/v1/items', json={'name': f'x{i}'}, headers={'Authorization': f'Bearer {access}'})
    r = client.get('/v1/items?page=2', headers={'Authorization': f'Bearer {access}'})
    assert r.status_code == 200
    data = r.get_json()
    assert data['page'] == 2
    assert data['per_page'] == 20
    assert len(data['items']) == 5

    # refresh
    r = client.post('/v1/auth/refresh', json={'refresh_token': refresh})
    assert r.status_code == 200
    new_tokens = r.get_json()
    assert 'access_token' in new_tokens and 'refresh_token' in new_tokens


def test_input_validation_and_audit_logs(client, app):
    register(client, username='dave')
    r = login(client, username='dave')
    tokens = r.get_json()
    access = tokens['access_token']

    # missing JSON
    r = client.post('/v1/items', headers={'Authorization': f'Bearer {access}'})
    assert r.status_code == 400

    # create
    r = client.post('/v1/items', json={'name': 'aaa'}, headers={'Authorization': f'Bearer {access}'})
    assert r.status_code == 201
    # check audit log created
    with app.app_context():
        logs = AuditLog.query.filter_by(action='create').all()
        assert len(logs) >= 1

    # update
    item_id = r.get_json()['id']
    r = client.put(f'/v1/items/{item_id}', json={'name': 'bbb'}, headers={'Authorization': f'Bearer {access}'})
    assert r.status_code == 200
    with app.app_context():
        logs = AuditLog.query.filter_by(action='update').all()
        assert len(logs) >= 1

    # delete
    r = client.delete(f'/v1/items/{item_id}', headers={'Authorization': f'Bearer {access}'})
    assert r.status_code == 204
    with app.app_context():
        logs = AuditLog.query.filter_by(action='delete').all()
        assert len(logs) >= 1
