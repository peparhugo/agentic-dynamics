import json
import time
from models import db, User, Item, RefreshToken, AuditLog


def register(client, username='alice', password='password'):
    return client.post('/v1/register', json={'username': username, 'password': password})


def login(client, username='alice', password='password'):
    return client.post('/v1/login', json={'username': username, 'password': password})


def test_register_and_login_refresh(client, app):
    rv = register(client)
    assert rv.status_code == 201
    rv = login(client)
    assert rv.status_code == 200
    tokens = rv.get_json()
    assert 'access_token' in tokens and 'refresh_token' in tokens

    access = tokens['access_token']
    # try protected endpoint (list items)
    rv = client.get('/v1/items', headers={'Authorization': f'Bearer {access}'})
    assert rv.status_code == 200

    # refresh
    rv = client.post('/v1/refresh', json={'refresh_token': tokens['refresh_token']})
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'access_token' in data


def test_login_rate_limit(client, app):
    register(client, 'bob', 'pw')
    # 5 failed attempts
    for _ in range(5):
        rv = login(client, 'bob', 'wrong')
        assert rv.status_code == 401
    # 6th should be 429
    rv = login(client, 'bob', 'wrong')
    assert rv.status_code == 429
    # after a minute, should be allowed to attempt again; simulate by clearing limiter
    app.rate_limiter.clear()
    rv = login(client, 'bob', 'pw')
    assert rv.status_code == 200


def test_input_validation_and_pagination(client, app):
    register(client, 'carol', 'pw')
    rv = login(client, 'carol', 'pw')
    tokens = rv.get_json()
    access = tokens['access_token']

    # create item without title -> 400
    rv = client.post('/v1/items', json={'description': 'no title'}, headers={'Authorization': f'Bearer {access}'})
    assert rv.status_code == 400

    # create 50 items
    for i in range(50):
        rv = client.post('/v1/items', json={'title': f'item {i}', 'description': 'x'}, headers={'Authorization': f'Bearer {access}'})
        assert rv.status_code == 201

    # default pagination -> 20 items
    rv = client.get('/v1/items')
    data = rv.get_json()
    assert rv.status_code == 200
    assert data['per_page'] == 20
    assert len(data['items']) == 20

    # page 3 should have 10
    rv = client.get('/v1/items?page=3')
    data = rv.get_json()
    assert len(data['items']) == 10

    # per_page > 100 -> 400
    rv = client.get('/v1/items?per_page=200')
    assert rv.status_code == 400


def test_audit_logging(client, app):
    register(client, 'dave', 'pw')
    rv = login(client, 'dave', 'pw')
    access = rv.get_json()['access_token']

    # create item
    rv = client.post('/v1/items', json={'title': 'audit item'}, headers={'Authorization': f'Bearer {access}'})
    assert rv.status_code == 201
    item_id = rv.get_json()['id']
    # check audit log
    logs = AuditLog.query.filter_by(action='create_item').all()
    assert any(l.resource == f'item:{item_id}' for l in logs)

    # update
    rv = client.put(f'/v1/items/{item_id}', json={'title': 'updated'}, headers={'Authorization': f'Bearer {access}'})
    assert rv.status_code == 200
    logs = AuditLog.query.filter_by(action='update_item').all()
    assert any(l.resource == f'item:{item_id}' for l in logs)

    # delete
    rv = client.delete(f'/v1/items/{item_id}', headers={'Authorization': f'Bearer {access}'})
    assert rv.status_code == 200
    logs = AuditLog.query.filter_by(action='delete_item').all()
    assert any(l.resource == f'item:{item_id}' for l in logs)
