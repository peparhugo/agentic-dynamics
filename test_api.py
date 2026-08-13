import pytest
import json
import os
from datetime import datetime
from app import app, db, Task


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


class TestCreateTask:
    def test_create_task_success(self, client):
        response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Buy groceries'}),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['title'] == 'Buy groceries'
        assert data['status'] == 'pending'
        assert 'id' in data
        assert 'created_at' in data

    def test_create_task_missing_title(self, client):
        response = client.post(
            '/tasks',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_create_task_empty_title(self, client):
        response = client.post(
            '/tasks',
            data=json.dumps({'title': ''}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_create_task_no_json(self, client):
        response = client.post('/tasks')
        assert response.status_code == 400


class TestListTasks:
    def test_list_empty(self, client):
        response = client.get('/tasks')
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        client.post(
            '/tasks',
            data=json.dumps({'title': 'First task'}),
            content_type='application/json'
        )
        client.post(
            '/tasks',
            data=json.dumps({'title': 'Second task'}),
            content_type='application/json'
        )

        response = client.get('/tasks')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2
        assert data[0]['title'] == 'Second task'
        assert data[1]['title'] == 'First task'

    def test_list_includes_all_fields(self, client):
        client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json'
        )

        response = client.get('/tasks')
        data = response.get_json()
        assert 'id' in data[0]
        assert 'title' in data[0]
        assert 'status' in data[0]
        assert 'created_at' in data[0]


class TestGetTask:
    def test_get_task_success(self, client):
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json'
        )
        task_id = create_response.get_json()['id']

        response = client.get(f'/tasks/{task_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == task_id
        assert data['title'] == 'Test task'
        assert data['status'] == 'pending'

    def test_get_task_not_found(self, client):
        response = client.get('/tasks/999')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_get_task_includes_all_fields(self, client):
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json'
        )
        task_id = create_response.get_json()['id']

        response = client.get(f'/tasks/{task_id}')
        data = response.get_json()
        assert 'id' in data
        assert 'title' in data
        assert 'status' in data
        assert 'created_at' in data


class TestUpdateTask:
    def test_update_task_title(self, client):
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Original title'}),
            content_type='application/json'
        )
        task_id = create_response.get_json()['id']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'title': 'Updated title'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'Updated title'
        assert data['status'] == 'pending'

    def test_update_task_status(self, client):
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json'
        )
        task_id = create_response.get_json()['id']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'completed'
        assert data['title'] == 'Test task'

    def test_update_task_title_and_status(self, client):
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Original'}),
            content_type='application/json'
        )
        task_id = create_response.get_json()['id']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'title': 'New title', 'status': 'in_progress'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'New title'
        assert data['status'] == 'in_progress'

    def test_update_task_not_found(self, client):
        response = client.put(
            '/tasks/999',
            data=json.dumps({'title': 'Updated'}),
            content_type='application/json'
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_update_task_with_empty_values_ignores_them(self, client):
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json'
        )
        task_id = create_response.get_json()['id']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'title': '', 'status': ''}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'Test task'
        assert data['status'] == 'pending'

    def test_update_task_preserves_created_at(self, client):
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json'
        )
        task_id = create_response.get_json()['id']
        created_at = create_response.get_json()['created_at']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'title': 'Updated'}),
            content_type='application/json'
        )
        data = response.get_json()
        assert data['created_at'] == created_at
