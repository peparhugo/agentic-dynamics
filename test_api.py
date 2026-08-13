import pytest
import json
import os
from datetime import datetime
from app import app, db, Task, User


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def register_user(client, username, password):
    response = client.post(
        '/auth/register',
        data=json.dumps({'username': username, 'password': password}),
        content_type='application/json'
    )
    return response


def login_user(client, username, password):
    response = client.post(
        '/auth/login',
        data=json.dumps({'username': username, 'password': password}),
        content_type='application/json'
    )
    if response.status_code == 200:
        return response.get_json()['token']
    return None


class TestAuthRegister:
    def test_register_success(self, client):
        response = register_user(client, 'testuser', 'password123')
        assert response.status_code == 201
        data = response.get_json()
        assert data['username'] == 'testuser'
        assert 'id' in data
        assert 'created_at' in data

    def test_register_missing_username(self, client):
        response = client.post(
            '/auth/register',
            data=json.dumps({'password': 'password123'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_register_missing_password(self, client):
        response = client.post(
            '/auth/register',
            data=json.dumps({'username': 'testuser'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_register_empty_username(self, client):
        response = client.post(
            '/auth/register',
            data=json.dumps({'username': '', 'password': 'password123'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_register_empty_password(self, client):
        response = client.post(
            '/auth/register',
            data=json.dumps({'username': 'testuser', 'password': ''}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_register_duplicate_username(self, client):
        register_user(client, 'testuser', 'password123')
        response = register_user(client, 'testuser', 'different_password')
        assert response.status_code == 409
        data = response.get_json()
        assert 'error' in data

    def test_register_no_json(self, client):
        response = client.post('/auth/register')
        assert response.status_code == 400


class TestAuthLogin:
    def test_login_success(self, client):
        register_user(client, 'testuser', 'password123')
        response = login_user(client, 'testuser', 'password123')
        assert response is not None
        response = client.post(
            '/auth/login',
            data=json.dumps({'username': 'testuser', 'password': 'password123'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'token' in data

    def test_login_missing_username(self, client):
        response = client.post(
            '/auth/login',
            data=json.dumps({'password': 'password123'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_login_missing_password(self, client):
        response = client.post(
            '/auth/login',
            data=json.dumps({'username': 'testuser'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_login_invalid_username(self, client):
        response = client.post(
            '/auth/login',
            data=json.dumps({'username': 'nonexistent', 'password': 'password123'}),
            content_type='application/json'
        )
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_login_invalid_password(self, client):
        register_user(client, 'testuser', 'password123')
        response = client.post(
            '/auth/login',
            data=json.dumps({'username': 'testuser', 'password': 'wrongpassword'}),
            content_type='application/json'
        )
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_login_no_json(self, client):
        response = client.post('/auth/login')
        assert response.status_code == 400


class TestCreateTask:
    def test_create_task_success(self, client):
        token = login_user(client, *self._register_and_login(client))
        response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Buy groceries'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['title'] == 'Buy groceries'
        assert data['status'] == 'pending'
        assert 'id' in data
        assert 'created_at' in data
        assert 'owner_id' in data

    def test_create_task_missing_title(self, client):
        token = login_user(client, *self._register_and_login(client))
        response = client.post(
            '/tasks',
            data=json.dumps({}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_create_task_empty_title(self, client):
        token = login_user(client, *self._register_and_login(client))
        response = client.post(
            '/tasks',
            data=json.dumps({'title': ''}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_create_task_no_json(self, client):
        token = login_user(client, *self._register_and_login(client))
        response = client.post(
            '/tasks',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 400

    def test_create_task_without_token(self, client):
        response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Buy groceries'}),
            content_type='application/json'
        )
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_create_task_with_invalid_token(self, client):
        response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Buy groceries'}),
            content_type='application/json',
            headers={'Authorization': 'Bearer invalid_token'}
        )
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def _register_and_login(self, client):
        register_user(client, 'testuser', 'password123')
        return 'testuser', 'password123'


class TestListTasks:
    def test_list_empty(self, client):
        token = login_user(client, *self._register_and_login(client))
        response = client.get(
            '/tasks',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        token = login_user(client, *self._register_and_login(client))
        client.post(
            '/tasks',
            data=json.dumps({'title': 'First task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        client.post(
            '/tasks',
            data=json.dumps({'title': 'Second task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )

        response = client.get(
            '/tasks',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2
        assert data[0]['title'] == 'Second task'
        assert data[1]['title'] == 'First task'

    def test_list_includes_all_fields(self, client):
        token = login_user(client, *self._register_and_login(client))
        client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )

        response = client.get(
            '/tasks',
            headers={'Authorization': f'Bearer {token}'}
        )
        data = response.get_json()
        assert 'id' in data[0]
        assert 'title' in data[0]
        assert 'status' in data[0]
        assert 'created_at' in data[0]
        assert 'owner_id' in data[0]

    def test_list_tasks_without_token(self, client):
        response = client.get('/tasks')
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_list_tasks_only_shows_user_tasks(self, client):
        username1, password1 = 'user1', 'password1'
        username2, password2 = 'user2', 'password2'
        register_user(client, username1, password1)
        register_user(client, username2, password2)
        token1 = login_user(client, username1, password1)
        token2 = login_user(client, username2, password2)

        client.post(
            '/tasks',
            data=json.dumps({'title': 'User1 task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token1}'}
        )
        client.post(
            '/tasks',
            data=json.dumps({'title': 'User2 task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token2}'}
        )

        response1 = client.get(
            '/tasks',
            headers={'Authorization': f'Bearer {token1}'}
        )
        response2 = client.get(
            '/tasks',
            headers={'Authorization': f'Bearer {token2}'}
        )

        data1 = response1.get_json()
        data2 = response2.get_json()
        assert len(data1) == 1
        assert len(data2) == 1
        assert data1[0]['title'] == 'User1 task'
        assert data2[0]['title'] == 'User2 task'

    def _register_and_login(self, client):
        register_user(client, 'testuser', 'password123')
        return 'testuser', 'password123'


class TestGetTask:
    def test_get_task_success(self, client):
        token = login_user(client, *self._register_and_login(client))
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        task_id = create_response.get_json()['id']

        response = client.get(
            f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == task_id
        assert data['title'] == 'Test task'
        assert data['status'] == 'pending'

    def test_get_task_not_found(self, client):
        token = login_user(client, *self._register_and_login(client))
        response = client.get(
            '/tasks/999',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_get_task_includes_all_fields(self, client):
        token = login_user(client, *self._register_and_login(client))
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        task_id = create_response.get_json()['id']

        response = client.get(
            f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        data = response.get_json()
        assert 'id' in data
        assert 'title' in data
        assert 'status' in data
        assert 'created_at' in data
        assert 'owner_id' in data

    def test_get_task_without_token(self, client):
        response = client.get('/tasks/1')
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_get_task_cannot_access_other_user_task(self, client):
        username1, password1 = 'user1', 'password1'
        username2, password2 = 'user2', 'password2'
        register_user(client, username1, password1)
        register_user(client, username2, password2)
        token1 = login_user(client, username1, password1)
        token2 = login_user(client, username2, password2)

        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'User1 task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token1}'}
        )
        task_id = create_response.get_json()['id']

        response = client.get(
            f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {token2}'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def _register_and_login(self, client):
        register_user(client, 'testuser', 'password123')
        return 'testuser', 'password123'


class TestUpdateTask:
    def test_update_task_title(self, client):
        token = login_user(client, *self._register_and_login(client))
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Original title'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        task_id = create_response.get_json()['id']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'title': 'Updated title'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'Updated title'
        assert data['status'] == 'pending'

    def test_update_task_status(self, client):
        token = login_user(client, *self._register_and_login(client))
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        task_id = create_response.get_json()['id']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'completed'
        assert data['title'] == 'Test task'

    def test_update_task_title_and_status(self, client):
        token = login_user(client, *self._register_and_login(client))
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Original'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        task_id = create_response.get_json()['id']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'title': 'New title', 'status': 'in_progress'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'New title'
        assert data['status'] == 'in_progress'

    def test_update_task_not_found(self, client):
        token = login_user(client, *self._register_and_login(client))
        response = client.put(
            '/tasks/999',
            data=json.dumps({'title': 'Updated'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_update_task_with_empty_values_ignores_them(self, client):
        token = login_user(client, *self._register_and_login(client))
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        task_id = create_response.get_json()['id']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'title': '', 'status': ''}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'Test task'
        assert data['status'] == 'pending'

    def test_update_task_preserves_created_at(self, client):
        token = login_user(client, *self._register_and_login(client))
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        task_id = create_response.get_json()['id']
        created_at = create_response.get_json()['created_at']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'title': 'Updated'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        data = response.get_json()
        assert data['created_at'] == created_at

    def test_update_task_without_token(self, client):
        response = client.put(
            '/tasks/1',
            data=json.dumps({'title': 'Updated'}),
            content_type='application/json'
        )
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_update_task_cannot_modify_other_user_task(self, client):
        username1, password1 = 'user1', 'password1'
        username2, password2 = 'user2', 'password2'
        register_user(client, username1, password1)
        register_user(client, username2, password2)
        token1 = login_user(client, username1, password1)
        token2 = login_user(client, username2, password2)

        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'User1 task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token1}'}
        )
        task_id = create_response.get_json()['id']

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'title': 'Hacked title'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token2}'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def _register_and_login(self, client):
        register_user(client, 'testuser', 'password123')
        return 'testuser', 'password123'
