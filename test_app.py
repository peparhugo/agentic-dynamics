"""
Tests for the Task Management Flask API.
"""

import pytest
import json
import os
import tempfile
import shutil
from datetime import datetime
from app import (
    app, TASKS_FILE, STORAGE_DIR, USERS_FILE,
    _load_tasks, _save_tasks, _load_users, _save_users,
    _ensure_storage, _migrate_tasks_to_add_owner
)


@pytest.fixture
def client():
    """Create a test client with a temporary storage directory."""
    # Create a temporary directory for test data
    test_dir = tempfile.mkdtemp()

    # Patch the STORAGE_DIR and TASKS_FILE in the app module
    import app as app_module
    original_storage_dir = app_module.STORAGE_DIR
    original_tasks_file = app_module.TASKS_FILE
    original_users_file = app_module.USERS_FILE

    app_module.STORAGE_DIR = test_dir
    app_module.TASKS_FILE = os.path.join(test_dir, "tasks.json")
    app_module.USERS_FILE = os.path.join(test_dir, "users.json")

    # Configure app for testing
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client

    # Cleanup
    app_module.STORAGE_DIR = original_storage_dir
    app_module.TASKS_FILE = original_tasks_file
    app_module.USERS_FILE = original_users_file
    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def authenticated_client(client):
    """Create an authenticated test client with a registered user."""
    # Register a test user
    register_response = client.post('/auth/register',
        json={"username": "testuser", "password": "testpass123"},
        content_type='application/json'
    )
    assert register_response.status_code == 201

    # Login to get token
    login_response = client.post('/auth/login',
        json={"username": "testuser", "password": "testpass123"},
        content_type='application/json'
    )
    assert login_response.status_code == 200
    token = json.loads(login_response.data)['token']

    # Create a wrapper to automatically add auth header
    class AuthenticatedClient:
        def __init__(self, test_client, token):
            self.client = test_client
            self.token = token

        def _add_auth(self, kwargs):
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = f'Bearer {self.token}'
            return kwargs

        def get(self, *args, **kwargs):
            return self.client.get(*args, **self._add_auth(kwargs))

        def post(self, *args, **kwargs):
            return self.client.post(*args, **self._add_auth(kwargs))

        def put(self, *args, **kwargs):
            return self.client.put(*args, **self._add_auth(kwargs))

    return AuthenticatedClient(client, token)


class TestAuth:
    def test_register_success(self, client):
        """Test successful user registration."""
        response = client.post('/auth/register',
            json={"username": "alice", "password": "password123"},
            content_type='application/json'
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['username'] == 'alice'
        assert 'id' in data
        assert 'password_hash' not in data

    def test_register_missing_username(self, client):
        """Test registration without username."""
        response = client.post('/auth/register',
            json={"password": "password123"},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_register_missing_password(self, client):
        """Test registration without password."""
        response = client.post('/auth/register',
            json={"username": "alice"},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_register_duplicate_username(self, client):
        """Test registration with duplicate username."""
        client.post('/auth/register',
            json={"username": "alice", "password": "password123"},
            content_type='application/json'
        )
        response = client.post('/auth/register',
            json={"username": "alice", "password": "different"},
            content_type='application/json'
        )
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'exists' in data['error'].lower()

    def test_login_success(self, client):
        """Test successful login."""
        client.post('/auth/register',
            json={"username": "bob", "password": "secret"},
            content_type='application/json'
        )
        response = client.post('/auth/login',
            json={"username": "bob", "password": "secret"},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'token' in data

    def test_login_invalid_username(self, client):
        """Test login with invalid username."""
        response = client.post('/auth/login',
            json={"username": "nonexistent", "password": "password"},
            content_type='application/json'
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_invalid_password(self, client):
        """Test login with invalid password."""
        client.post('/auth/register',
            json={"username": "charlie", "password": "correct"},
            content_type='application/json'
        )
        response = client.post('/auth/login',
            json={"username": "charlie", "password": "wrong"},
            content_type='application/json'
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_missing_username(self, client):
        """Test login without username."""
        response = client.post('/auth/login',
            json={"password": "password"},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_missing_password(self, client):
        """Test login without password."""
        response = client.post('/auth/login',
            json={"username": "user"},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data


class TestAuthProtection:
    def test_create_task_without_auth(self, client):
        """Test that task creation requires auth."""
        response = client.post('/tasks',
            json={"title": "Task"},
            content_type='application/json'
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_task_invalid_token(self, client):
        """Test that invalid token is rejected."""
        response = client.post('/tasks',
            json={"title": "Task"},
            content_type='application/json',
            headers={'Authorization': 'Bearer invalid-token'}
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data

    def test_list_tasks_without_auth(self, client):
        """Test that list tasks requires auth."""
        response = client.get('/tasks')
        assert response.status_code == 401

    def test_get_task_without_auth(self, client):
        """Test that get task requires auth."""
        response = client.get('/tasks/1')
        assert response.status_code == 401

    def test_update_task_without_auth(self, client):
        """Test that update task requires auth."""
        response = client.put('/tasks/1',
            json={"title": "Updated"},
            content_type='application/json'
        )
        assert response.status_code == 401


class TestCreateTask:
    def test_create_task_success(self, authenticated_client):
        """Test successful task creation."""
        response = authenticated_client.post('/tasks',
            json={"title": "Buy groceries"},
            content_type='application/json'
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['title'] == 'Buy groceries'
        assert data['status'] == 'pending'
        assert data['id'] == 1
        assert 'created_at' in data
        assert 'owner_id' in data

    def test_create_task_missing_title(self, authenticated_client):
        """Test task creation without title."""
        response = authenticated_client.post('/tasks',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'title' in data['error'].lower()

    def test_create_task_empty_title(self, authenticated_client):
        """Test task creation with empty title."""
        response = authenticated_client.post('/tasks',
            json={"title": "   "},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_task_no_json(self, authenticated_client):
        """Test task creation without JSON body."""
        response = authenticated_client.post('/tasks')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_multiple_tasks(self, authenticated_client):
        """Test creating multiple tasks."""
        response1 = authenticated_client.post('/tasks',
            json={"title": "Task 1"},
            content_type='application/json'
        )
        response2 = authenticated_client.post('/tasks',
            json={"title": "Task 2"},
            content_type='application/json'
        )

        assert response1.status_code == 201
        assert response2.status_code == 201

        data1 = json.loads(response1.data)
        data2 = json.loads(response2.data)

        assert data1['id'] == 1
        assert data2['id'] == 2


class TestListTasks:
    def test_list_empty_tasks(self, authenticated_client):
        """Test listing tasks when none exist."""
        response = authenticated_client.get('/tasks')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    def test_list_tasks_ordered_by_created_at_desc(self, authenticated_client):
        """Test that tasks are ordered by created_at descending."""
        # Create tasks
        authenticated_client.post('/tasks', json={"title": "Task 1"}, content_type='application/json')
        authenticated_client.post('/tasks', json={"title": "Task 2"}, content_type='application/json')
        authenticated_client.post('/tasks', json={"title": "Task 3"}, content_type='application/json')

        response = authenticated_client.get('/tasks')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert len(data) == 3
        # Should be ordered by created_at descending (most recent first)
        assert data[0]['title'] == 'Task 3'
        assert data[1]['title'] == 'Task 2'
        assert data[2]['title'] == 'Task 1'

    def test_list_tasks_multiple(self, authenticated_client):
        """Test listing multiple tasks."""
        authenticated_client.post('/tasks', json={"title": "Task 1"}, content_type='application/json')
        authenticated_client.post('/tasks', json={"title": "Task 2"}, content_type='application/json')

        response = authenticated_client.get('/tasks')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2

    def test_list_tasks_isolated_by_user(self, client):
        """Test that users only see their own tasks."""
        # Register and login first user
        client.post('/auth/register',
            json={"username": "alice", "password": "pass1"},
            content_type='application/json'
        )
        login1 = client.post('/auth/login',
            json={"username": "alice", "password": "pass1"},
            content_type='application/json'
        )
        token1 = json.loads(login1.data)['token']

        # Register and login second user
        client.post('/auth/register',
            json={"username": "bob", "password": "pass2"},
            content_type='application/json'
        )
        login2 = client.post('/auth/login',
            json={"username": "bob", "password": "pass2"},
            content_type='application/json'
        )
        token2 = json.loads(login2.data)['token']

        # First user creates a task
        client.post('/tasks',
            json={"title": "Alice's task"},
            content_type='application/json',
            headers={'Authorization': f'Bearer {token1}'}
        )

        # Second user creates a task
        client.post('/tasks',
            json={"title": "Bob's task"},
            content_type='application/json',
            headers={'Authorization': f'Bearer {token2}'}
        )

        # First user should only see their task
        resp1 = client.get('/tasks', headers={'Authorization': f'Bearer {token1}'})
        tasks1 = json.loads(resp1.data)
        assert len(tasks1) == 1
        assert tasks1[0]['title'] == "Alice's task"

        # Second user should only see their task
        resp2 = client.get('/tasks', headers={'Authorization': f'Bearer {token2}'})
        tasks2 = json.loads(resp2.data)
        assert len(tasks2) == 1
        assert tasks2[0]['title'] == "Bob's task"


class TestGetTask:
    def test_get_task_success(self, authenticated_client):
        """Test getting a single task."""
        create_response = authenticated_client.post('/tasks',
            json={"title": "Buy milk"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = authenticated_client.get(f'/tasks/{task_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Buy milk'
        assert data['id'] == task_id

    def test_get_task_not_found(self, authenticated_client):
        """Test getting a non-existent task."""
        response = authenticated_client.get('/tasks/999')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert 'not found' in data['error'].lower()

    def test_get_task_invalid_id(self, authenticated_client):
        """Test getting a task with invalid ID format."""
        response = authenticated_client.get('/tasks/invalid')
        assert response.status_code == 404

    def test_get_task_not_owned(self, client):
        """Test that users cannot access tasks from other users."""
        # Register and create a task as first user
        client.post('/auth/register',
            json={"username": "alice", "password": "pass1"},
            content_type='application/json'
        )
        login1 = client.post('/auth/login',
            json={"username": "alice", "password": "pass1"},
            content_type='application/json'
        )
        token1 = json.loads(login1.data)['token']

        create_resp = client.post('/tasks',
            json={"title": "Alice's secret task"},
            content_type='application/json',
            headers={'Authorization': f'Bearer {token1}'}
        )
        task_id = json.loads(create_resp.data)['id']

        # Register and login as second user
        client.post('/auth/register',
            json={"username": "bob", "password": "pass2"},
            content_type='application/json'
        )
        login2 = client.post('/auth/login',
            json={"username": "bob", "password": "pass2"},
            content_type='application/json'
        )
        token2 = json.loads(login2.data)['token']

        # Second user should not be able to access first user's task
        response = client.get(f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {token2}'}
        )
        assert response.status_code == 404


class TestUpdateTask:
    def test_update_task_title(self, authenticated_client):
        """Test updating a task's title."""
        create_response = authenticated_client.post('/tasks',
            json={"title": "Old title"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = authenticated_client.put(f'/tasks/{task_id}',
            json={"title": "New title"},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'New title'
        assert data['status'] == 'pending'

    def test_update_task_status(self, authenticated_client):
        """Test updating a task's status."""
        create_response = authenticated_client.post('/tasks',
            json={"title": "Task"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = authenticated_client.put(f'/tasks/{task_id}',
            json={"status": "completed"},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'completed'
        assert data['title'] == 'Task'

    def test_update_task_title_and_status(self, authenticated_client):
        """Test updating both title and status."""
        create_response = authenticated_client.post('/tasks',
            json={"title": "Original"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = authenticated_client.put(f'/tasks/{task_id}',
            json={"title": "Updated", "status": "in_progress"},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Updated'
        assert data['status'] == 'in_progress'

    def test_update_task_not_found(self, authenticated_client):
        """Test updating a non-existent task."""
        response = authenticated_client.put('/tasks/999',
            json={"title": "New title"},
            content_type='application/json'
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_task_empty_update(self, authenticated_client):
        """Test updating a task with empty JSON."""
        create_response = authenticated_client.post('/tasks',
            json={"title": "Task"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = authenticated_client.put(f'/tasks/{task_id}',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Task'
        assert data['status'] == 'pending'

    def test_update_task_empty_title_ignored(self, authenticated_client):
        """Test that empty title is ignored in update."""
        create_response = authenticated_client.post('/tasks',
            json={"title": "Original"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = authenticated_client.put(f'/tasks/{task_id}',
            json={"title": "   "},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        # Title should remain unchanged since empty strings are stripped
        assert data['title'] == 'Original'

    def test_update_task_not_owned(self, client):
        """Test that users cannot update tasks from other users."""
        # Register and create a task as first user
        client.post('/auth/register',
            json={"username": "alice", "password": "pass1"},
            content_type='application/json'
        )
        login1 = client.post('/auth/login',
            json={"username": "alice", "password": "pass1"},
            content_type='application/json'
        )
        token1 = json.loads(login1.data)['token']

        create_resp = client.post('/tasks',
            json={"title": "Alice's task"},
            content_type='application/json',
            headers={'Authorization': f'Bearer {token1}'}
        )
        task_id = json.loads(create_resp.data)['id']

        # Register and login as second user
        client.post('/auth/register',
            json={"username": "bob", "password": "pass2"},
            content_type='application/json'
        )
        login2 = client.post('/auth/login',
            json={"username": "bob", "password": "pass2"},
            content_type='application/json'
        )
        token2 = json.loads(login2.data)['token']

        # Second user should not be able to update first user's task
        response = client.put(f'/tasks/{task_id}',
            json={"title": "Hacked"},
            content_type='application/json',
            headers={'Authorization': f'Bearer {token2}'}
        )
        assert response.status_code == 404


class TestHealth:
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'


class TestIntegration:
    def test_full_workflow(self, authenticated_client):
        """Test a complete workflow: create, list, get, update."""
        # Create task
        create_resp = authenticated_client.post('/tasks',
            json={"title": "Complete project"},
            content_type='application/json'
        )
        assert create_resp.status_code == 201
        task = json.loads(create_resp.data)
        task_id = task['id']

        # List tasks
        list_resp = authenticated_client.get('/tasks')
        assert list_resp.status_code == 200
        tasks = json.loads(list_resp.data)
        assert len(tasks) == 1

        # Get task
        get_resp = authenticated_client.get(f'/tasks/{task_id}')
        assert get_resp.status_code == 200
        task = json.loads(get_resp.data)
        assert task['title'] == 'Complete project'

        # Update task
        update_resp = authenticated_client.put(f'/tasks/{task_id}',
            json={"status": "completed"},
            content_type='application/json'
        )
        assert update_resp.status_code == 200
        updated = json.loads(update_resp.data)
        assert updated['status'] == 'completed'

        # Verify update
        get_resp2 = authenticated_client.get(f'/tasks/{task_id}')
        task = json.loads(get_resp2.data)
        assert task['status'] == 'completed'

    def test_persistence_across_requests(self, authenticated_client):
        """Test that data persists across requests."""
        # Create multiple tasks
        for i in range(3):
            authenticated_client.post('/tasks',
                json={"title": f"Task {i+1}"},
                content_type='application/json'
            )

        # List and verify
        resp1 = authenticated_client.get('/tasks')
        data1 = json.loads(resp1.data)
        assert len(data1) == 3

        # List again and verify same data
        resp2 = authenticated_client.get('/tasks')
        data2 = json.loads(resp2.data)
        assert len(data2) == 3
        assert data1 == data2
