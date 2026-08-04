import os
import tempfile
import json
import pytest


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    monkeypatch.setenv('TASKS_DB', db_path)
    # ensure fresh import
    import importlib.util
    # load app.py directly to ensure it's found regardless of cwd/module path
    app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app.py'))
    spec = importlib.util.spec_from_file_location('app', app_path)
    _app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_app)
    yield


@pytest.fixture
def client():
    import importlib.util, os
    app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app.py'))
    spec = importlib.util.spec_from_file_location('app', app_path)
    app_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_mod)
    app_ = app_mod.create_app()
    return app_.test_client()


def register(client, username, password):
    r = client.post('/register', json={'username': username, 'password': password})
    return r


def login(client, username, password):
    r = client.post('/login', json={'username': username, 'password': password})
    return r


def auth_header(token):
    return {'Authorization': f'Bearer {token}'}


def test_user_registration_and_login(client):
    r = register(client, 'alice', 'password')
    assert r.status_code == 201
    data = r.get_json()
    assert data['username'] == 'alice'

    # duplicate username
    r2 = register(client, 'alice', 'password')
    assert r2.status_code == 400

    # login
    r3 = login(client, 'alice', 'password')
    assert r3.status_code == 200
    token = r3.get_json()['token']
    assert token

    # wrong creds
    r4 = login(client, 'alice', 'wrong')
    assert r4.status_code == 401


def test_task_crud_and_permissions(client):
    # create users
    register(client, 'creator', 'pw')
    register(client, 'assignee', 'pw')
    t1 = login(client, 'creator', 'pw').get_json()['token']
    t2 = login(client, 'assignee', 'pw').get_json()['token']

    # create a task
    res = client.post('/tasks', json={'title': 'Task 1', 'description': 'Do stuff', 'priority': 'high'}, headers=auth_header(t1))
    assert res.status_code == 201
    task = res.get_json()['task']
    tid = task['id']
    assert task['title'] == 'Task 1'

    # get task
    res = client.get(f'/tasks/{tid}', headers=auth_header(t1))
    assert res.status_code == 200

    # assignee cannot delete (only creator can)
    res = client.delete(f'/tasks/{tid}', headers=auth_header(t2))
    assert res.status_code == 403

    # assign task to assignee
    res = client.put(f'/tasks/{tid}', json={'assignee_id': 2}, headers=auth_header(t1))
    assert res.status_code == 200
    task = res.get_json()['task']
    assert task['assignee_id'] == 2

    # assignee can update
    res = client.put(f'/tasks/{tid}', json={'status': 'in_progress'}, headers=auth_header(t2))
    assert res.status_code == 200
    task = res.get_json()['task']
    assert task['status'] == 'in_progress'

    # creator deletes
    res = client.delete(f'/tasks/{tid}', headers=auth_header(t1))
    assert res.status_code == 200

    # now not found
    res = client.get(f'/tasks/{tid}', headers=auth_header(t1))
    assert res.status_code == 404


def test_pagination_search_and_filters(client):
    register(client, 'u1', 'pw')
    token = login(client, 'u1', 'pw').get_json()['token']
    headers = auth_header(token)
    # create 25 tasks
    for i in range(25):
        client.post('/tasks', json={'title': f'Task {i}', 'description': f'Desc {i}', 'category': 'cat' + str(i%3), 'priority': ['low','medium','high'][i%3]}, headers=headers)

    # page 1 per_page 10
    r = client.get('/tasks?page=1&per_page=10', headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data['total'] == 25
    assert len(data['tasks']) == 10

    # search for text
    r = client.get('/tasks?q=Task 1', headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data['total'] >= 2  # Task 1 and Task 10,11,12...

    # filter by category
    r = client.get('/tasks?category=cat1', headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    for t in data['tasks']:
        assert t['category'] == 'cat1'

    # filter by priority
    r = client.get('/tasks?priority=high', headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    for t in data['tasks']:
        assert t['priority'] == 'high'


def test_due_date_filters_and_assignment(client):
    register(client, 'owner', 'pw')
    register(client, 'bob', 'pw')
    owner_t = login(client, 'owner', 'pw').get_json()['token']
    bob_t = login(client, 'bob', 'pw').get_json()['token']
    hdr = auth_header(owner_t)
    # create tasks with due dates
    client.post('/tasks', json={'title':'A','due_date':'2026-01-01','assignee_id':2}, headers=hdr)
    client.post('/tasks', json={'title':'B','due_date':'2026-06-01'}, headers=hdr)
    client.post('/tasks', json={'title':'C','due_date':'2027-01-01','assignee_id':2}, headers=hdr)

    # due_before
    r = client.get('/tasks?due_before=2026-12-31', headers=hdr)
    assert r.status_code == 200
    data = r.get_json()
    assert any(t['title']=='A' for t in data['tasks'])

    # assignee filter
    r = client.get('/tasks?assignee_id=2', headers=hdr)
    assert r.status_code == 200
    data = r.get_json()
    assert all(t.get('assignee_id') == 2 for t in data['tasks'])
