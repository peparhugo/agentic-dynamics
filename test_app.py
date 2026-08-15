"""
Tests for the Task Management Flask API.
"""

import pytest
import json
import os
import tempfile
import shutil
from datetime import datetime
from app import app, TASKS_FILE, STORAGE_DIR, _load_tasks, _save_tasks, _ensure_storage


@pytest.fixture
def client():
    """Create a test client with a temporary storage directory."""
    # Create a temporary directory for test data
    test_dir = tempfile.mkdtemp()

    # Patch the STORAGE_DIR and TASKS_FILE in the app module
    import app as app_module
    original_storage_dir = app_module.STORAGE_DIR
    original_tasks_file = app_module.TASKS_FILE

    app_module.STORAGE_DIR = test_dir
    app_module.TASKS_FILE = os.path.join(test_dir, "tasks.json")

    # Configure app for testing
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client

    # Cleanup
    app_module.STORAGE_DIR = original_storage_dir
    app_module.TASKS_FILE = original_tasks_file
    shutil.rmtree(test_dir, ignore_errors=True)


class TestCreateTask:
    def test_create_task_success(self, client):
        """Test successful task creation."""
        response = client.post('/tasks',
            json={"title": "Buy groceries"},
            content_type='application/json'
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['title'] == 'Buy groceries'
        assert data['status'] == 'pending'
        assert data['id'] == 1
        assert 'created_at' in data

    def test_create_task_missing_title(self, client):
        """Test task creation without title."""
        response = client.post('/tasks',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'title' in data['error'].lower()

    def test_create_task_empty_title(self, client):
        """Test task creation with empty title."""
        response = client.post('/tasks',
            json={"title": "   "},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_task_no_json(self, client):
        """Test task creation without JSON body."""
        response = client.post('/tasks')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_multiple_tasks(self, client):
        """Test creating multiple tasks."""
        response1 = client.post('/tasks',
            json={"title": "Task 1"},
            content_type='application/json'
        )
        response2 = client.post('/tasks',
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
    def test_list_empty_tasks(self, client):
        """Test listing tasks when none exist."""
        response = client.get('/tasks')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        """Test that tasks are ordered by created_at descending."""
        # Create tasks
        client.post('/tasks', json={"title": "Task 1"}, content_type='application/json')
        client.post('/tasks', json={"title": "Task 2"}, content_type='application/json')
        client.post('/tasks', json={"title": "Task 3"}, content_type='application/json')

        response = client.get('/tasks')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert len(data) == 3
        # Should be ordered by created_at descending (most recent first)
        assert data[0]['title'] == 'Task 3'
        assert data[1]['title'] == 'Task 2'
        assert data[2]['title'] == 'Task 1'

    def test_list_tasks_multiple(self, client):
        """Test listing multiple tasks."""
        client.post('/tasks', json={"title": "Task 1"}, content_type='application/json')
        client.post('/tasks', json={"title": "Task 2"}, content_type='application/json')

        response = client.get('/tasks')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2


class TestGetTask:
    def test_get_task_success(self, client):
        """Test getting a single task."""
        create_response = client.post('/tasks',
            json={"title": "Buy milk"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = client.get(f'/tasks/{task_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Buy milk'
        assert data['id'] == task_id

    def test_get_task_not_found(self, client):
        """Test getting a non-existent task."""
        response = client.get('/tasks/999')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert 'not found' in data['error'].lower()

    def test_get_task_invalid_id(self, client):
        """Test getting a task with invalid ID format."""
        response = client.get('/tasks/invalid')
        assert response.status_code == 404


class TestUpdateTask:
    def test_update_task_title(self, client):
        """Test updating a task's title."""
        create_response = client.post('/tasks',
            json={"title": "Old title"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = client.put(f'/tasks/{task_id}',
            json={"title": "New title"},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'New title'
        assert data['status'] == 'pending'

    def test_update_task_status(self, client):
        """Test updating a task's status."""
        create_response = client.post('/tasks',
            json={"title": "Task"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = client.put(f'/tasks/{task_id}',
            json={"status": "completed"},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'completed'
        assert data['title'] == 'Task'

    def test_update_task_title_and_status(self, client):
        """Test updating both title and status."""
        create_response = client.post('/tasks',
            json={"title": "Original"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = client.put(f'/tasks/{task_id}',
            json={"title": "Updated", "status": "in_progress"},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Updated'
        assert data['status'] == 'in_progress'

    def test_update_task_not_found(self, client):
        """Test updating a non-existent task."""
        response = client.put('/tasks/999',
            json={"title": "New title"},
            content_type='application/json'
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_task_empty_update(self, client):
        """Test updating a task with empty JSON."""
        create_response = client.post('/tasks',
            json={"title": "Task"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = client.put(f'/tasks/{task_id}',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Task'
        assert data['status'] == 'pending'

    def test_update_task_empty_title_ignored(self, client):
        """Test that empty title is ignored in update."""
        create_response = client.post('/tasks',
            json={"title": "Original"},
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['id']

        response = client.put(f'/tasks/{task_id}',
            json={"title": "   "},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        # Title should remain unchanged since empty strings are stripped
        assert data['title'] == 'Original'


class TestHealth:
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'


class TestIntegration:
    def test_full_workflow(self, client):
        """Test a complete workflow: create, list, get, update."""
        # Create task
        create_resp = client.post('/tasks',
            json={"title": "Complete project"},
            content_type='application/json'
        )
        assert create_resp.status_code == 201
        task = json.loads(create_resp.data)
        task_id = task['id']

        # List tasks
        list_resp = client.get('/tasks')
        assert list_resp.status_code == 200
        tasks = json.loads(list_resp.data)
        assert len(tasks) == 1

        # Get task
        get_resp = client.get(f'/tasks/{task_id}')
        assert get_resp.status_code == 200
        task = json.loads(get_resp.data)
        assert task['title'] == 'Complete project'

        # Update task
        update_resp = client.put(f'/tasks/{task_id}',
            json={"status": "completed"},
            content_type='application/json'
        )
        assert update_resp.status_code == 200
        updated = json.loads(update_resp.data)
        assert updated['status'] == 'completed'

        # Verify update
        get_resp2 = client.get(f'/tasks/{task_id}')
        task = json.loads(get_resp2.data)
        assert task['status'] == 'completed'

    def test_persistence_across_requests(self, client):
        """Test that data persists across requests."""
        # Create multiple tasks
        for i in range(3):
            client.post('/tasks',
                json={"title": f"Task {i+1}"},
                content_type='application/json'
            )

        # List and verify
        resp1 = client.get('/tasks')
        data1 = json.loads(resp1.data)
        assert len(data1) == 3

        # List again and verify same data
        resp2 = client.get('/tasks')
        data2 = json.loads(resp2.data)
        assert len(data2) == 3
        assert data1 == data2
