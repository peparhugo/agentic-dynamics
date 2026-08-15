import pytest
import json
import os
from unittest.mock import patch, MagicMock
from app import app, STORAGE_FILE, USERS_FILE

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
    if os.path.exists(STORAGE_FILE):
        os.remove(STORAGE_FILE)
    if os.path.exists(USERS_FILE):
        os.remove(USERS_FILE)

@pytest.fixture
def cleanup():
    yield
    if os.path.exists(STORAGE_FILE):
        os.remove(STORAGE_FILE)
    if os.path.exists(USERS_FILE):
        os.remove(USERS_FILE)

@pytest.fixture
def auth_headers(client, cleanup):
    """Helper to register and get auth token"""
    def _get_token(username='testuser', password='testpass', email='testuser@example.com'):
        client.post('/auth/register',
            json={'username': username, 'password': password, 'email': email},
            content_type='application/json'
        )
        response = client.post('/auth/login',
            json={'username': username, 'password': password},
            content_type='application/json'
        )
        token = response.get_json()['token']
        return {'Authorization': f'Bearer {token}'}
    return _get_token

def test_register_success(client, cleanup):
    response = client.post('/auth/register',
        json={'username': 'newuser', 'password': 'password123', 'email': 'newuser@example.com'},
        content_type='application/json'
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data['username'] == 'newuser'
    assert data['email'] == 'newuser@example.com'
    assert data['id'] == 1
    assert 'created_at' in data

def test_register_missing_username(client, cleanup):
    response = client.post('/auth/register',
        json={'password': 'password123', 'email': 'test@example.com'},
        content_type='application/json'
    )
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data

def test_register_missing_password(client, cleanup):
    response = client.post('/auth/register',
        json={'username': 'newuser', 'email': 'test@example.com'},
        content_type='application/json'
    )
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data

def test_register_duplicate_username(client, cleanup):
    client.post('/auth/register',
        json={'username': 'testuser', 'password': 'pass1', 'email': 'user1@example.com'},
        content_type='application/json'
    )
    response = client.post('/auth/register',
        json={'username': 'testuser', 'password': 'pass2', 'email': 'user2@example.com'},
        content_type='application/json'
    )
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data

def test_login_success(client, cleanup):
    client.post('/auth/register',
        json={'username': 'testuser', 'password': 'testpass', 'email': 'test@example.com'},
        content_type='application/json'
    )
    response = client.post('/auth/login',
        json={'username': 'testuser', 'password': 'testpass'},
        content_type='application/json'
    )
    assert response.status_code == 200
    data = response.get_json()
    assert 'token' in data

def test_login_invalid_credentials(client, cleanup):
    client.post('/auth/register',
        json={'username': 'testuser', 'password': 'testpass', 'email': 'test@example.com'},
        content_type='application/json'
    )
    response = client.post('/auth/login',
        json={'username': 'testuser', 'password': 'wrongpass'},
        content_type='application/json'
    )
    assert response.status_code == 401
    data = response.get_json()
    assert 'error' in data

def test_login_nonexistent_user(client, cleanup):
    response = client.post('/auth/login',
        json={'username': 'nouser', 'password': 'pass'},
        content_type='application/json'
    )
    assert response.status_code == 401
    data = response.get_json()
    assert 'error' in data

def test_create_task_success(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data['title'] == 'Test Task'
    assert data['status'] == 'pending'
    assert data['id'] == 1
    assert 'created_at' in data
    assert data['owner_id'] == 1

def test_create_task_missing_token(client, cleanup):
    response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json'
    )
    assert response.status_code == 401
    data = response.get_json()
    assert 'error' in data

def test_create_task_invalid_token(client, cleanup):
    response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json',
        headers={'Authorization': 'Bearer invalid_token'}
    )
    assert response.status_code == 401
    data = response.get_json()
    assert 'error' in data

def test_create_task_missing_title(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    response = client.post('/tasks',
        json={},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data

def test_create_task_empty_title(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    response = client.post('/tasks',
        json={'title': ''},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data

def test_create_task_with_status(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    response = client.post('/tasks',
        json={'title': 'Test Task', 'status': 'completed'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data['status'] == 'completed'
    assert data['owner_id'] == 1

def test_list_tasks_empty(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    response = client.get('/tasks', headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data == []

def test_list_tasks_missing_token(client, cleanup):
    response = client.get('/tasks')
    assert response.status_code == 401
    data = response.get_json()
    assert 'error' in data

def test_list_tasks_ordered_by_created_at_desc(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    client.post('/tasks', json={'title': 'Task 1'}, content_type='application/json', headers=headers)
    client.post('/tasks', json={'title': 'Task 2'}, content_type='application/json', headers=headers)
    client.post('/tasks', json={'title': 'Task 3'}, content_type='application/json', headers=headers)

    response = client.get('/tasks', headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 3
    assert data[0]['title'] == 'Task 3'
    assert data[1]['title'] == 'Task 2'
    assert data[2]['title'] == 'Task 1'

def test_list_tasks_user_isolation(client, cleanup, auth_headers):
    headers1 = auth_headers('user1', 'pass1')
    headers2 = auth_headers('user2', 'pass2')

    client.post('/tasks', json={'title': 'User1 Task 1'}, content_type='application/json', headers=headers1)
    client.post('/tasks', json={'title': 'User1 Task 2'}, content_type='application/json', headers=headers1)
    client.post('/tasks', json={'title': 'User2 Task 1'}, content_type='application/json', headers=headers2)

    response1 = client.get('/tasks', headers=headers1)
    data1 = response1.get_json()
    assert len(data1) == 2
    assert all(t['owner_id'] == 1 for t in data1)

    response2 = client.get('/tasks', headers=headers2)
    data2 = response2.get_json()
    assert len(data2) == 1
    assert all(t['owner_id'] == 2 for t in data2)

def test_get_task_success(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    create_response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.get(f'/tasks/{task_id}', headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data['id'] == task_id
    assert data['title'] == 'Test Task'
    assert data['status'] == 'pending'
    assert data['owner_id'] == 1

def test_get_task_missing_token(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    create_response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.get(f'/tasks/{task_id}')
    assert response.status_code == 401
    data = response.get_json()
    assert 'error' in data

def test_get_task_not_found(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    response = client.get('/tasks/999', headers=headers)
    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data

def test_get_task_unauthorized(client, cleanup, auth_headers):
    headers1 = auth_headers('user1', 'pass1')
    headers2 = auth_headers('user2', 'pass2')

    create_response = client.post('/tasks',
        json={'title': 'User1 Task'},
        content_type='application/json',
        headers=headers1
    )
    task_id = create_response.get_json()['id']

    response = client.get(f'/tasks/{task_id}', headers=headers2)
    assert response.status_code == 403
    data = response.get_json()
    assert 'error' in data

def test_update_task_title(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    create_response = client.post('/tasks',
        json={'title': 'Original Title'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'title': 'Updated Title'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'Updated Title'
    assert data['id'] == task_id

def test_update_task_status(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    create_response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'status': 'completed'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'completed'
    assert data['title'] == 'Test Task'

def test_update_task_title_and_status(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    create_response = client.post('/tasks',
        json={'title': 'Original Title'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'title': 'New Title', 'status': 'in_progress'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'New Title'
    assert data['status'] == 'in_progress'

def test_update_task_missing_token(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    create_response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'title': 'New Title'},
        content_type='application/json'
    )
    assert response.status_code == 401
    data = response.get_json()
    assert 'error' in data

def test_update_task_not_found(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    response = client.put('/tasks/999',
        json={'title': 'New Title'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data

def test_update_task_unauthorized(client, cleanup, auth_headers):
    headers1 = auth_headers('user1', 'pass1')
    headers2 = auth_headers('user2', 'pass2')

    create_response = client.post('/tasks',
        json={'title': 'User1 Task'},
        content_type='application/json',
        headers=headers1
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'title': 'Updated Title'},
        content_type='application/json',
        headers=headers2
    )
    assert response.status_code == 403
    data = response.get_json()
    assert 'error' in data

def test_persistence(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    create_response = client.post('/tasks',
        json={'title': 'Persistent Task'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    with app.test_client() as new_client:
        response = new_client.get(f'/tasks/{task_id}', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'Persistent Task'

def test_multiple_tasks_auto_increment(client, cleanup, auth_headers):
    headers = auth_headers('user1', 'pass1')
    r1 = client.post('/tasks', json={'title': 'Task 1'}, content_type='application/json', headers=headers)
    r2 = client.post('/tasks', json={'title': 'Task 2'}, content_type='application/json', headers=headers)
    r3 = client.post('/tasks', json={'title': 'Task 3'}, content_type='application/json', headers=headers)

    id1 = r1.get_json()['id']
    id2 = r2.get_json()['id']
    id3 = r3.get_json()['id']

    assert id1 == 1
    assert id2 == 2
    assert id3 == 3

@patch('app.send_notification_email.delay')
def test_notification_sent_on_task_completion(mock_send_email, client, cleanup, auth_headers):
    """Test that notification is triggered when task status changes to completed"""
    headers = auth_headers('user1', 'pass1', 'user1@example.com')
    create_response = client.post('/tasks',
        json={'title': 'Important Task'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'status': 'completed'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 200

    mock_send_email.assert_called_once_with('user1@example.com', 'Important Task')

@patch('app.send_notification_email.delay')
def test_notification_not_sent_on_other_status_changes(mock_send_email, client, cleanup, auth_headers):
    """Test that notification is NOT triggered for non-completed status changes"""
    headers = auth_headers('user1', 'pass1', 'user1@example.com')
    create_response = client.post('/tasks',
        json={'title': 'Test Task'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'status': 'in_progress'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 200

    mock_send_email.assert_not_called()

@patch('app.send_notification_email.delay')
def test_notification_not_sent_when_already_completed(mock_send_email, client, cleanup, auth_headers):
    """Test that notification is NOT triggered if status is already completed"""
    headers = auth_headers('user1', 'pass1', 'user1@example.com')
    create_response = client.post('/tasks',
        json={'title': 'Test Task', 'status': 'completed'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'status': 'completed'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 200

    mock_send_email.assert_not_called()

@patch('app.send_notification_email.delay')
def test_notification_sent_with_correct_task_title(mock_send_email, client, cleanup, auth_headers):
    """Test that notification is sent with the correct task title"""
    headers = auth_headers('user1', 'pass1', 'user1@example.com')
    create_response = client.post('/tasks',
        json={'title': 'Complete this ASAP'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'status': 'completed'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 200

    mock_send_email.assert_called_once_with('user1@example.com', 'Complete this ASAP')

@patch('app.send_notification_email.delay')
def test_notification_with_status_and_title_update(mock_send_email, client, cleanup, auth_headers):
    """Test that notification is sent when both title and status are updated to completed"""
    headers = auth_headers('user1', 'pass1', 'user1@example.com')
    create_response = client.post('/tasks',
        json={'title': 'Original Title'},
        content_type='application/json',
        headers=headers
    )
    task_id = create_response.get_json()['id']

    response = client.put(f'/tasks/{task_id}',
        json={'title': 'Updated Title', 'status': 'completed'},
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'Updated Title'
    assert data['status'] == 'completed'

    mock_send_email.assert_called_once_with('user1@example.com', 'Updated Title')
