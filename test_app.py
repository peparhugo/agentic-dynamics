import pytest
import json
import os
import tempfile
from app import app, init_db
import sqlite3


@pytest.fixture
def client(monkeypatch):
    db_fd, db_path = tempfile.mkstemp()
    app.config['TESTING'] = True
    monkeypatch.setenv('DATABASE', db_path)

    # Re-import to get the updated DATABASE variable
    import app as app_module
    app_module.DATABASE = db_path

    with app.app_context():
        init_db()

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def sample_task(client):
    response = client.post('/tasks',
        data=json.dumps({'title': 'Test Task'}),
        content_type='application/json')
    return json.loads(response.data)


class TestCreateTask:
    def test_create_task_success(self, client):
        response = client.post('/tasks',
            data=json.dumps({'title': 'New Task'}),
            content_type='application/json')

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['title'] == 'New Task'
        assert data['status'] == 'pending'
        assert 'id' in data
        assert 'created_at' in data

    def test_create_task_missing_title(self, client):
        response = client.post('/tasks',
            data=json.dumps({}),
            content_type='application/json')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_task_empty_title(self, client):
        response = client.post('/tasks',
            data=json.dumps({'title': ''}),
            content_type='application/json')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_task_whitespace_title(self, client):
        response = client.post('/tasks',
            data=json.dumps({'title': '   '}),
            content_type='application/json')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data


class TestListTasks:
    def test_list_empty_tasks(self, client):
        response = client.get('/tasks')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    def test_list_multiple_tasks_ordered(self, client):
        client.post('/tasks',
            data=json.dumps({'title': 'Task 1'}),
            content_type='application/json')
        client.post('/tasks',
            data=json.dumps({'title': 'Task 2'}),
            content_type='application/json')
        client.post('/tasks',
            data=json.dumps({'title': 'Task 3'}),
            content_type='application/json')

        response = client.get('/tasks')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 3
        assert data[0]['title'] == 'Task 3'
        assert data[1]['title'] == 'Task 2'
        assert data[2]['title'] == 'Task 1'

    def test_list_tasks_has_required_fields(self, client):
        client.post('/tasks',
            data=json.dumps({'title': 'Test Task'}),
            content_type='application/json')

        response = client.get('/tasks')
        data = json.loads(response.data)

        assert len(data) == 1
        assert 'id' in data[0]
        assert 'title' in data[0]
        assert 'status' in data[0]
        assert 'created_at' in data[0]


class TestGetTask:
    def test_get_task_success(self, client, sample_task):
        task_id = sample_task['id']
        response = client.get(f'/tasks/{task_id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == task_id
        assert data['title'] == 'Test Task'
        assert data['status'] == 'pending'

    def test_get_task_not_found(self, client):
        response = client.get('/tasks/9999')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_get_task_returns_correct_fields(self, client, sample_task):
        task_id = sample_task['id']
        response = client.get(f'/tasks/{task_id}')
        data = json.loads(response.data)

        assert 'id' in data
        assert 'title' in data
        assert 'status' in data
        assert 'created_at' in data


class TestUpdateTask:
    def test_update_task_title(self, client, sample_task):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'title': 'Updated Title'}),
            content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Updated Title'
        assert data['status'] == 'pending'

    def test_update_task_status(self, client, sample_task):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Test Task'
        assert data['status'] == 'completed'

    def test_update_task_title_and_status(self, client, sample_task):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'title': 'New Title', 'status': 'in_progress'}),
            content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'New Title'
        assert data['status'] == 'in_progress'

    def test_update_task_not_found(self, client):
        response = client.put('/tasks/9999',
            data=json.dumps({'title': 'Updated'}),
            content_type='application/json')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_task_empty_fields(self, client, sample_task):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({}),
            content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Test Task'
        assert data['status'] == 'pending'

    def test_update_persists_changes(self, client, sample_task):
        task_id = sample_task['id']
        client.put(f'/tasks/{task_id}',
            data=json.dumps({'title': 'Persisted Title', 'status': 'done'}),
            content_type='application/json')

        response = client.get(f'/tasks/{task_id}')
        data = json.loads(response.data)
        assert data['title'] == 'Persisted Title'
        assert data['status'] == 'done'


class TestIntegration:
    def test_full_workflow(self, client):
        # Create task
        response = client.post('/tasks',
            data=json.dumps({'title': 'Integration Test'}),
            content_type='application/json')
        task = json.loads(response.data)
        task_id = task['id']

        # Get task
        response = client.get(f'/tasks/{task_id}')
        assert response.status_code == 200

        # Update task
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json')
        assert response.status_code == 200

        # Verify in list
        response = client.get('/tasks')
        data = json.loads(response.data)
        assert any(t['id'] == task_id and t['status'] == 'completed' for t in data)

    def test_multiple_tasks_isolation(self, client):
        # Create multiple tasks
        response1 = client.post('/tasks',
            data=json.dumps({'title': 'Task 1'}),
            content_type='application/json')
        task1 = json.loads(response1.data)

        response2 = client.post('/tasks',
            data=json.dumps({'title': 'Task 2'}),
            content_type='application/json')
        task2 = json.loads(response2.data)

        # Update task1
        client.put(f'/tasks/{task1["id"]}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json')

        # Verify task2 is unchanged
        response = client.get(f'/tasks/{task2["id"]}')
        data = json.loads(response.data)
        assert data['status'] == 'pending'
