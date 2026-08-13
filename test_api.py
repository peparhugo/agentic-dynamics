import pytest
import json
import os
from datetime import datetime
from unittest import mock
from app import app, db, Task, User
import redis


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    # Flush Redis to reset rate limiting between tests
    try:
        r = redis.from_url('redis://localhost:6379/1')
        r.flushdb()
    except:
        pass

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()

    # Flush Redis after test
    try:
        r = redis.from_url('redis://localhost:6379/1')
        r.flushdb()
    except:
        pass


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
        assert data['data'] == []
        assert data['next_cursor'] is None
        assert data['total'] == 0

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
        assert len(data['data']) == 2
        assert data['data'][0]['title'] == 'Second task'
        assert data['data'][1]['title'] == 'First task'

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
        assert 'id' in data['data'][0]
        assert 'title' in data['data'][0]
        assert 'status' in data['data'][0]
        assert 'created_at' in data['data'][0]
        assert 'owner_id' in data['data'][0]

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
        assert len(data1['data']) == 1
        assert len(data2['data']) == 1
        assert data1['data'][0]['title'] == 'User1 task'
        assert data2['data'][0]['title'] == 'User2 task'

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


class TestNotificationTrigger:
    @mock.patch('app.send_notification_email.delay')
    def test_notification_triggered_on_status_change_to_completed(self, mock_send_email, client):
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
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] is None
        assert call_args[0][1] == 'Test task'

    @mock.patch('app.send_notification_email.delay')
    def test_notification_triggered_with_user_email(self, mock_send_email, client):
        register_response = client.post(
            '/auth/register',
            data=json.dumps({'username': 'testuser', 'password': 'password123', 'email': 'test@example.com'}),
            content_type='application/json'
        )
        token = login_user(client, 'testuser', 'password123')

        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Important task'}),
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
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] == 'test@example.com'
        assert call_args[0][1] == 'Important task'

    @mock.patch('app.send_notification_email.delay')
    def test_notification_not_triggered_on_other_status_changes(self, mock_send_email, client):
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
            data=json.dumps({'status': 'in_progress'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        mock_send_email.assert_not_called()

    @mock.patch('app.send_notification_email.delay')
    def test_notification_not_triggered_when_already_completed(self, mock_send_email, client):
        token = login_user(client, *self._register_and_login(client))
        create_response = client.post(
            '/tasks',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        task_id = create_response.get_json()['id']

        client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        mock_send_email.reset_mock()

        response = client.put(
            f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        mock_send_email.assert_not_called()

    @mock.patch('app.send_notification_email.delay')
    def test_notification_triggered_when_updating_title_and_status_to_completed(self, mock_send_email, client):
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
            data=json.dumps({'title': 'Updated title', 'status': 'completed'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][1] == 'Updated title'

    def _register_and_login(self, client):
        register_user(client, 'testuser', 'password123')
        return 'testuser', 'password123'


class TestPaginationListTasks:
    def test_list_tasks_pagination_default_limit(self, client):
        token = login_user(client, *self._register_and_login(client))
        for i in range(5):
            client.post(
                '/tasks',
                data=json.dumps({'title': f'Task {i}'}),
                content_type='application/json',
                headers={'Authorization': f'Bearer {token}'}
            )

        response = client.get(
            '/tasks',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'data' in data
        assert 'next_cursor' in data
        assert 'total' in data
        assert len(data['data']) == 5
        assert data['total'] == 5
        assert data['next_cursor'] is None

    def test_list_tasks_pagination_with_cursor(self, client):
        token = login_user(client, *self._register_and_login(client))
        for i in range(25):
            client.post(
                '/tasks',
                data=json.dumps({'title': f'Task {i}'}),
                content_type='application/json',
                headers={'Authorization': f'Bearer {token}'}
            )

        response = client.get(
            '/tasks?limit=10',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['data']) == 10
        assert data['total'] == 25
        assert data['next_cursor'] is not None

        cursor = data['next_cursor']
        response2 = client.get(
            f'/tasks?cursor={cursor}&limit=10',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response2.status_code == 200
        data2 = response2.get_json()
        assert len(data2['data']) == 10
        assert data2['total'] == 25
        assert data2['next_cursor'] is not None

        cursor2 = data2['next_cursor']
        response3 = client.get(
            f'/tasks?cursor={cursor2}&limit=10',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response3.status_code == 200
        data3 = response3.get_json()
        assert len(data3['data']) == 5
        assert data3['total'] == 25
        assert data3['next_cursor'] is None

    def test_list_tasks_pagination_custom_limit(self, client):
        token = login_user(client, *self._register_and_login(client))
        for i in range(15):
            client.post(
                '/tasks',
                data=json.dumps({'title': f'Task {i}'}),
                content_type='application/json',
                headers={'Authorization': f'Bearer {token}'}
            )

        response = client.get(
            '/tasks?limit=5',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['data']) == 5
        assert data['total'] == 15
        assert data['next_cursor'] is not None

    def test_list_tasks_pagination_invalid_limit_too_high(self, client):
        token = login_user(client, *self._register_and_login(client))
        for i in range(50):
            client.post(
                '/tasks',
                data=json.dumps({'title': f'Task {i}'}),
                content_type='application/json',
                headers={'Authorization': f'Bearer {token}'}
            )

        response = client.get(
            '/tasks?limit=150',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['data']) == 20
        assert data['total'] == 50

    def test_list_tasks_pagination_invalid_limit_zero(self, client):
        token = login_user(client, *self._register_and_login(client))
        for i in range(5):
            client.post(
                '/tasks',
                data=json.dumps({'title': f'Task {i}'}),
                content_type='application/json',
                headers={'Authorization': f'Bearer {token}'}
            )

        response = client.get(
            '/tasks?limit=0',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['data']) == 5

    def test_list_tasks_pagination_empty_result(self, client):
        token = login_user(client, *self._register_and_login(client))
        response = client.get(
            '/tasks',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['data'] == []
        assert data['next_cursor'] is None
        assert data['total'] == 0

    def _register_and_login(self, client):
        register_user(client, 'testuser', 'password123')
        return 'testuser', 'password123'


class TestRateLimiting:
    @pytest.fixture
    def redis_conn(self):
        try:
            conn = redis.from_url('redis://localhost:6379/1')
            conn.ping()
            return conn
        except:
            pytest.skip("Redis not available")

    def test_rate_limiting_register_endpoint(self, client, redis_conn):
        redis_conn.flushdb()

        for i in range(101):
            response = client.post(
                '/auth/register',
                data=json.dumps({'username': f'user{i}', 'password': 'password123'}),
                content_type='application/json'
            )
            if i < 100:
                assert response.status_code == 201
            else:
                assert response.status_code == 429

    def test_rate_limiting_authenticated_user(self, client, redis_conn):
        redis_conn.flushdb()

        register_user(client, 'testuser', 'password123')
        token = login_user(client, 'testuser', 'password123')

        for i in range(101):
            response = client.get(
                '/tasks',
                headers={'Authorization': f'Bearer {token}'}
            )
            if i < 100:
                assert response.status_code == 200
            else:
                assert response.status_code == 429

    def test_rate_limiting_per_user_isolation(self, client, redis_conn):
        redis_conn.flushdb()

        username1, password1 = 'user1', 'password1'
        username2, password2 = 'user2', 'password2'
        register_user(client, username1, password1)
        register_user(client, username2, password2)
        token1 = login_user(client, username1, password1)
        token2 = login_user(client, username2, password2)

        for i in range(50):
            response1 = client.get(
                '/tasks',
                headers={'Authorization': f'Bearer {token1}'}
            )
            assert response1.status_code == 200

        for i in range(50):
            response2 = client.get(
                '/tasks',
                headers={'Authorization': f'Bearer {token2}'}
            )
            assert response2.status_code == 200

        for i in range(51):
            response1 = client.get(
                '/tasks',
                headers={'Authorization': f'Bearer {token1}'}
            )
            if i < 50:
                assert response1.status_code == 200
            else:
                assert response1.status_code == 429
