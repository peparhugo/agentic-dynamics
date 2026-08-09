import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app, db, User, RefreshToken, AuditLog
import json

@pytest.fixture(autouse=True)
def clean_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
    # reset in-memory rate limiter
    from app import rate_store
    rate_store.clear()
    yield

def register(client, username, password):
    return client.post('/v1/auth/register', json={'username':username,'password':password})

def login(client, username, password):
    return client.post('/v1/auth/login', json={'username':username,'password':password})

def test_register_login_refresh():
    client = app.test_client()
    r = register(client,'alice','pass1')
    assert r.status_code == 201
    r = login(client,'alice','pass1')
    assert r.status_code == 200
    data = r.get_json()
    assert 'access_token' in data and 'refresh_token' in data
    rt = data['refresh_token']
    r2 = client.post('/v1/auth/refresh', json={'refresh_token':rt})
    assert r2.status_code == 200
    assert 'access_token' in r2.get_json()

def test_login_rate_limit():
    client = app.test_client()
    register(client,'bob','pwd1')
    for i in range(5):
        r = login(client,'bob','wrong')
    r6 = login(client,'bob','wrong')
    assert r6.status_code == 429

def test_pagination_and_auth_required():
    client = app.test_client()
    for i in range(30):
        register(client,f'u{i}','pass')
    r = client.get('/v1/users')
    assert r.status_code == 401
    r = login(client,'u0','pass')
    tok = r.get_json()['access_token']
    h = {'Authorization':f'Bearer {tok}'}
    r1 = client.get('/v1/users?page=1&per_page=20', headers=h)
    assert r1.status_code == 200
    data = r1.get_json()
    assert data['total'] == 30
    assert len(data['items']) == 20
    r2 = client.get('/v1/users?page=2&per_page=20', headers=h)
    assert len(r2.get_json()['items']) == 10

def test_audit_log_on_mutations():
    client = app.test_client()
    register(client,'carol','pw12')
    r = login(client,'carol','pw12')
    tok = r.get_json()['access_token']
    h = {'Authorization':f'Bearer {tok}'}
    # update
    r1 = client.put('/v1/users/1', json={'username':'carol2'}, headers=h)
    assert r1.status_code == 200
    with app.app_context():
        logs = AuditLog.query.filter_by(action='update').all()
        assert len(logs) == 1
    # delete
    r2 = client.delete('/v1/users/1', headers=h)
    assert r2.status_code == 204
    with app.app_context():
        logs = AuditLog.query.filter_by(action='delete').all()
        assert len(logs) == 1
