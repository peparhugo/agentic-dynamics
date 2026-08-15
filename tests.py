import pytest
import json
import os
from app import app, STORAGE_FILE

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
    if os.path.exists(STORAGE_FILE):
        os.remove(STORAGE_FILE)

@pytest.fixture
def cleanup():
    yield
    if os.path.exists(STORAGE_FILE):
        os.remove(STORAGE_FILE)

def test_create_task_success(client, cleanup):
    response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json'
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data['title'] == 'Test Task'
    assert data['status'] == 'pending'
    assert data['id'] == 1
    assert 'created_at' in data

def test_create_task_missing_title(client, cleanup):
    response = client.post('/tasks',
        json={},
        content_type='application/json'
    )
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data

def test_create_task_empty_title(client, cleanup):
    response = client.post('/tasks',
        json={'title': ''},
        content_type='application/json'
    )
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data

def test_create_task_with_status(client, cleanup):
    response = client.post('/tasks',
        json={'title': 'Test Task', 'status': 'completed'},
        content_type='application/json'
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data['status'] == 'completed'

def test_list_tasks_empty(client, cleanup):
    response = client.get('/tasks')
    assert response.status_code == 200
    data = response.get_json()
    assert data == []

def test_list_tasks_ordered_by_created_at_desc(client, cleanup):
    client.post('/tasks', json={'title': 'Task 1'}, content_type='application/json')
    client.post('/tasks', json={'title': 'Task 2'}, content_type='application/json')
    client.post('/tasks', json={'title': 'Task 3'}, content_type='application/json')

    response = client.get('/tasks')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 3
    assert data[0]['title'] == 'Task 3'
    assert data[1]['title'] == 'Task 2'
    assert data[2]['title'] == 'Task 1'

def test_get_task_success(client, cleanup):
    create_response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json'
    )
    task_id = create_response.get_json()['id']

    response = client.get(f'/tasks/{task_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['id'] == task_id
    assert data['title'] == 'Test Task'
    assert data['status'] == 'pending'

def test_get_task_not_found(client, cleanup):
    response = client.get('/tasks/999')
    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data

def test_update_task_title(client, cleanup):
    create_response = client.post('/tasks',
        json={'title': 'Original Title'},
        content_type='application/json'
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'title': 'Updated Title'},
        content_type='application/json'
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'Updated Title'
    assert data['id'] == task_id

def test_update_task_status(client, cleanup):
    create_response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json'
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'status': 'completed'},
        content_type='application/json'
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'completed'
    assert data['title'] == 'Test Task'

def test_update_task_title_and_status(client, cleanup):
    create_response = client.post('/tasks',
        json={'title': 'Original Title'},
        content_type='application/json'
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'title': 'New Title', 'status': 'in_progress'},
        content_type='application/json'
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'New Title'
    assert data['status'] == 'in_progress'

def test_update_task_not_found(client, cleanup):
    response = client.put('/tasks/999',
        json={'title': 'New Title'},
        content_type='application/json'
    )
    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data

def test_persistence(client, cleanup):
    create_response = client.post('/tasks',
        json={'title': 'Persistent Task'},
        content_type='application/json'
    )
    task_id = create_response.get_json()['id']

    with app.test_client() as new_client:
        response = new_client.get(f'/tasks/{task_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'Persistent Task'

def test_multiple_tasks_auto_increment(client, cleanup):
    r1 = client.post('/tasks', json={'title': 'Task 1'}, content_type='application/json')
    r2 = client.post('/tasks', json={'title': 'Task 2'}, content_type='application/json')
    r3 = client.post('/tasks', json={'title': 'Task 3'}, content_type='application/json')

    id1 = r1.get_json()['id']
    id2 = r2.get_json()['id']
    id3 = r3.get_json()['id']

    assert id1 == 1
    assert id2 == 2
    assert id3 == 3
