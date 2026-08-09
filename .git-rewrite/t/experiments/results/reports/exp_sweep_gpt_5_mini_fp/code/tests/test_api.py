import pytest
from app import db
from models import User, Item, RefreshToken, AuditLog

def register(client, u='alice', p='pass'):
    return client.post('/v1/register', json={'username':u,'password':p})

def login(client, u='alice', p='pass'):
    return client.post('/v1/login', json={'username':u,'password':p})

def test_register_login_refresh_and_rate_limit(client):
    r = register(client)
    assert r.status_code==201
    r = login(client)
    assert r.status_code==200
    tokens = r.get_json()
    assert 'access_token' in tokens and 'refresh_token' in tokens
    rt = client.post('/v1/refresh', json={'refresh_token':tokens['refresh_token']})
    assert rt.status_code==200
    for _ in range(5):
        client.post('/v1/login', json={'username':'alice','password':'wrong'})
    r = client.post('/v1/login', json={'username':'alice','password':'wrong'})
    assert r.status_code==429

def test_item_crud_and_audit_and_pagination(client, app):
    client.post('/v1/register', json={'username':'bob','password':'pw'})
    r = client.post('/v1/login', json={'username':'bob','password':'pw'})
    tokens = r.get_json()
    headers = {'Authorization':f"Bearer {tokens['access_token']}"}
    rv = client.post('/v1/items', json={'name':'it1'}, headers=headers)
    assert rv.status_code==201
    data = rv.get_json()
    assert data['name']=='it1'
    # update
    rv = client.put(f"/v1/items/{data['id']}", json={'name':'changed'}, headers=headers)
    assert rv.status_code==200
    # bad update
    rv = client.put(f"/v1/items/{data['id']}", json={'name':''}, headers=headers)
    assert rv.status_code==400
    # create many items for pagination
    for i in range(50):
        client.post('/v1/items', json={'name':f'n{i}'}, headers=headers)
    r = client.get('/v1/items?page=1&per_page=20')
    j = r.get_json()
    assert r.status_code==200
    assert len(j['items'])==20
    assert j['per_page']==20
    # per_page too large
    r = client.get('/v1/items?per_page=101')
    assert r.status_code==400
    # delete
    rv = client.delete(f"/v1/items/{data['id']}", headers=headers)
    assert rv.status_code==204
    # audit logs exist
    with app.app_context():
        logs = AuditLog.query.all()
        assert any(l.operation=='create' for l in logs)
        assert any(l.operation=='update' for l in logs)
        assert any(l.operation=='delete' for l in logs)

def test_versioning_and_input_validation(client):
    r = client.post('/v1/register', json={'username':'x'})
    assert r.status_code==400
    r = client.get('/notv1/items')
    assert r.status_code==404
