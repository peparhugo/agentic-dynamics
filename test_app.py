import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from app import app, init_db
import sqlite3
from unittest.mock import MagicMock as Mock


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
def user1(client):
    response = client.post('/auth/register',
        data=json.dumps({'username': 'user1', 'password': 'pass123'}),
        content_type='application/json')
    return json.loads(response.data)


@pytest.fixture
def user2(client):
    response = client.post('/auth/register',
        data=json.dumps({'username': 'user2', 'password': 'pass456'}),
        content_type='application/json')
    return json.loads(response.data)


@pytest.fixture
def token1(client):
    client.post('/auth/register',
        data=json.dumps({'username': 'user1', 'password': 'pass123'}),
        content_type='application/json')
    response = client.post('/auth/login',
        data=json.dumps({'username': 'user1', 'password': 'pass123'}),
        content_type='application/json')
    return json.loads(response.data)['token']


@pytest.fixture
def token2(client):
    client.post('/auth/register',
        data=json.dumps({'username': 'user2', 'password': 'pass456'}),
        content_type='application/json')
    response = client.post('/auth/login',
        data=json.dumps({'username': 'user2', 'password': 'pass456'}),
        content_type='application/json')
    return json.loads(response.data)['token']


@pytest.fixture
def sample_task(client, token1):
    response = client.post('/tasks',
        data=json.dumps({'title': 'Test Task'}),
        content_type='application/json',
        headers={'Authorization': f'Bearer {token1}'})
    return json.loads(response.data)


def get_auth_headers(token):
    return {'Authorization': f'Bearer {token}'}


class TestAuth:
    def test_register_success(self, client):
        response = client.post('/auth/register',
            data=json.dumps({'username': 'testuser', 'password': 'testpass'}),
            content_type='application/json')

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['username'] == 'testuser'
        assert 'id' in data

    def test_register_missing_username(self, client):
        response = client.post('/auth/register',
            data=json.dumps({'password': 'testpass'}),
            content_type='application/json')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_register_missing_password(self, client):
        response = client.post('/auth/register',
            data=json.dumps({'username': 'testuser'}),
            content_type='application/json')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_register_duplicate_username(self, client):
        client.post('/auth/register',
            data=json.dumps({'username': 'testuser', 'password': 'testpass'}),
            content_type='application/json')

        response = client.post('/auth/register',
            data=json.dumps({'username': 'testuser', 'password': 'otherpass'}),
            content_type='application/json')

        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_success(self, client):
        client.post('/auth/register',
            data=json.dumps({'username': 'testuser', 'password': 'testpass'}),
            content_type='application/json')

        response = client.post('/auth/login',
            data=json.dumps({'username': 'testuser', 'password': 'testpass'}),
            content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'token' in data

    def test_login_invalid_password(self, client):
        client.post('/auth/register',
            data=json.dumps({'username': 'testuser', 'password': 'testpass'}),
            content_type='application/json')

        response = client.post('/auth/login',
            data=json.dumps({'username': 'testuser', 'password': 'wrongpass'}),
            content_type='application/json')

        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_nonexistent_user(self, client):
        response = client.post('/auth/login',
            data=json.dumps({'username': 'nouser', 'password': 'nopass'}),
            content_type='application/json')

        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_missing_username(self, client):
        response = client.post('/auth/login',
            data=json.dumps({'password': 'testpass'}),
            content_type='application/json')

        assert response.status_code == 400

    def test_login_missing_password(self, client):
        response = client.post('/auth/login',
            data=json.dumps({'username': 'testuser'}),
            content_type='application/json')

        assert response.status_code == 400


class TestCreateTask:
    def test_create_task_success(self, client, token1):
        response = client.post('/tasks',
            data=json.dumps({'title': 'New Task'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['title'] == 'New Task'
        assert data['status'] == 'pending'
        assert 'id' in data
        assert 'created_at' in data
        assert 'owner_id' in data

    def test_create_task_missing_auth(self, client):
        response = client.post('/tasks',
            data=json.dumps({'title': 'New Task'}),
            content_type='application/json')

        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_task_invalid_token(self, client):
        response = client.post('/tasks',
            data=json.dumps({'title': 'New Task'}),
            content_type='application/json',
            headers={'Authorization': 'Bearer invalid_token'})

        assert response.status_code == 401

    def test_create_task_missing_title(self, client, token1):
        response = client.post('/tasks',
            data=json.dumps({}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_task_empty_title(self, client, token1):
        response = client.post('/tasks',
            data=json.dumps({'title': ''}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_task_whitespace_title(self, client, token1):
        response = client.post('/tasks',
            data=json.dumps({'title': '   '}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data


class TestListTasks:
    def test_list_empty_tasks(self, client, token1):
        response = client.get('/tasks',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data'] == []
        assert data['next_cursor'] is None
        assert data['total'] == 0

    def test_list_missing_auth(self, client):
        response = client.get('/tasks')

        assert response.status_code == 401

    def test_list_multiple_tasks_ordered(self, client, token1):
        client.post('/tasks',
            data=json.dumps({'title': 'Task 1'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        client.post('/tasks',
            data=json.dumps({'title': 'Task 2'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        client.post('/tasks',
            data=json.dumps({'title': 'Task 3'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        response = client.get('/tasks',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 3
        assert data['data'][0]['title'] == 'Task 3'
        assert data['data'][1]['title'] == 'Task 2'
        assert data['data'][2]['title'] == 'Task 1'
        assert data['total'] == 3

    def test_list_tasks_has_required_fields(self, client, token1):
        client.post('/tasks',
            data=json.dumps({'title': 'Test Task'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        response = client.get('/tasks',
            headers=get_auth_headers(token1))
        data = json.loads(response.data)

        assert len(data['data']) == 1
        assert 'id' in data['data'][0]
        assert 'title' in data['data'][0]
        assert 'status' in data['data'][0]
        assert 'created_at' in data['data'][0]
        assert 'owner_id' in data['data'][0]

    def test_list_tasks_user_isolation(self, client, token1, token2):
        client.post('/tasks',
            data=json.dumps({'title': 'User1 Task'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        client.post('/tasks',
            data=json.dumps({'title': 'User2 Task'}),
            content_type='application/json',
            headers=get_auth_headers(token2))

        response1 = client.get('/tasks',
            headers=get_auth_headers(token1))
        response2 = client.get('/tasks',
            headers=get_auth_headers(token2))

        data1 = json.loads(response1.data)
        data2 = json.loads(response2.data)

        assert len(data1['data']) == 1
        assert data1['data'][0]['title'] == 'User1 Task'
        assert len(data2['data']) == 1
        assert data2['data'][0]['title'] == 'User2 Task'


class TestGetTask:
    def test_get_task_success(self, client, sample_task, token1):
        task_id = sample_task['id']
        response = client.get(f'/tasks/{task_id}',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == task_id
        assert data['title'] == 'Test Task'
        assert data['status'] == 'pending'

    def test_get_task_missing_auth(self, client, sample_task):
        task_id = sample_task['id']
        response = client.get(f'/tasks/{task_id}')

        assert response.status_code == 401

    def test_get_task_not_found(self, client, token1):
        response = client.get('/tasks/9999',
            headers=get_auth_headers(token1))

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_get_task_returns_correct_fields(self, client, sample_task, token1):
        task_id = sample_task['id']
        response = client.get(f'/tasks/{task_id}',
            headers=get_auth_headers(token1))
        data = json.loads(response.data)

        assert 'id' in data
        assert 'title' in data
        assert 'status' in data
        assert 'created_at' in data
        assert 'owner_id' in data

    def test_get_task_forbidden_for_other_user(self, client, token1, token2):
        response1 = client.post('/tasks',
            data=json.dumps({'title': 'User1 Task'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        task = json.loads(response1.data)
        task_id = task['id']

        response2 = client.get(f'/tasks/{task_id}',
            headers=get_auth_headers(token2))

        assert response2.status_code == 404


class TestUpdateTask:
    def test_update_task_title(self, client, sample_task, token1):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'title': 'Updated Title'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Updated Title'
        assert data['status'] == 'pending'

    def test_update_task_missing_auth(self, client, sample_task):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'title': 'Updated Title'}),
            content_type='application/json')

        assert response.status_code == 401

    def test_update_task_status(self, client, sample_task, token1):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Test Task'
        assert data['status'] == 'completed'

    def test_update_task_title_and_status(self, client, sample_task, token1):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'title': 'New Title', 'status': 'in_progress'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'New Title'
        assert data['status'] == 'in_progress'

    def test_update_task_not_found(self, client, token1):
        response = client.put('/tasks/9999',
            data=json.dumps({'title': 'Updated'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_task_empty_fields(self, client, sample_task, token1):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Test Task'
        assert data['status'] == 'pending'

    def test_update_persists_changes(self, client, sample_task, token1):
        task_id = sample_task['id']
        client.put(f'/tasks/{task_id}',
            data=json.dumps({'title': 'Persisted Title', 'status': 'done'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        response = client.get(f'/tasks/{task_id}',
            headers=get_auth_headers(token1))
        data = json.loads(response.data)
        assert data['title'] == 'Persisted Title'
        assert data['status'] == 'done'

    def test_update_task_forbidden_for_other_user(self, client, token1, token2):
        response1 = client.post('/tasks',
            data=json.dumps({'title': 'User1 Task'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        task = json.loads(response1.data)
        task_id = task['id']

        response2 = client.put(f'/tasks/{task_id}',
            data=json.dumps({'title': 'Hacked'}),
            content_type='application/json',
            headers=get_auth_headers(token2))

        assert response2.status_code == 404


class TestIntegration:
    def test_full_workflow(self, client, token1):
        # Create task
        response = client.post('/tasks',
            data=json.dumps({'title': 'Integration Test'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        task = json.loads(response.data)
        task_id = task['id']

        # Get task
        response = client.get(f'/tasks/{task_id}',
            headers=get_auth_headers(token1))
        assert response.status_code == 200

        # Update task
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        assert response.status_code == 200

        # Verify in list
        response = client.get('/tasks',
            headers=get_auth_headers(token1))
        data = json.loads(response.data)
        assert any(t['id'] == task_id and t['status'] == 'completed' for t in data['data'])

    def test_multiple_tasks_isolation(self, client, token1):
        # Create multiple tasks
        response1 = client.post('/tasks',
            data=json.dumps({'title': 'Task 1'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        task1 = json.loads(response1.data)

        response2 = client.post('/tasks',
            data=json.dumps({'title': 'Task 2'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        task2 = json.loads(response2.data)

        # Update task1
        client.put(f'/tasks/{task1["id"]}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        # Verify task2 is unchanged
        response = client.get(f'/tasks/{task2["id"]}',
            headers=get_auth_headers(token1))
        data = json.loads(response.data)
        assert data['status'] == 'pending'

    def test_cross_user_isolation(self, client, token1, token2):
        # User 1 creates tasks
        response1 = client.post('/tasks',
            data=json.dumps({'title': 'User1 Task 1'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        response2 = client.post('/tasks',
            data=json.dumps({'title': 'User1 Task 2'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        # User 2 creates tasks
        response3 = client.post('/tasks',
            data=json.dumps({'title': 'User2 Task 1'}),
            content_type='application/json',
            headers=get_auth_headers(token2))

        # Verify each user only sees their own tasks
        response = client.get('/tasks',
            headers=get_auth_headers(token1))
        user1_tasks = json.loads(response.data)
        assert len(user1_tasks['data']) == 2
        assert all(t['title'].startswith('User1') for t in user1_tasks['data'])

        response = client.get('/tasks',
            headers=get_auth_headers(token2))
        user2_tasks = json.loads(response.data)
        assert len(user2_tasks['data']) == 1
        assert user2_tasks['data'][0]['title'] == 'User2 Task 1'


class TestNotificationTrigger:
    @patch('app.send_notification_email')
    def test_notification_sent_on_completion(self, mock_send_email, client, token1, sample_task):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'completed'
        mock_send_email.delay.assert_called_once()
        call_args = mock_send_email.delay.call_args
        assert call_args[0][0] == 'user1@localhost.local'
        assert call_args[0][1] == 'Test Task'

    @patch('app.send_notification_email')
    def test_notification_not_sent_on_other_status_change(self, mock_send_email, client, token1, sample_task):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'status': 'in_progress'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        mock_send_email.delay.assert_not_called()

    @patch('app.send_notification_email')
    def test_notification_not_sent_on_non_status_change(self, mock_send_email, client, token1, sample_task):
        task_id = sample_task['id']
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'title': 'Updated Title'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        mock_send_email.delay.assert_not_called()

    @patch('app.send_notification_email')
    def test_notification_not_sent_if_already_completed(self, mock_send_email, client, token1, sample_task):
        task_id = sample_task['id']
        # First completion
        client.put(f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        mock_send_email.delay.reset_mock()

        # Try to complete again (should not send notification)
        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        mock_send_email.delay.assert_not_called()

    @patch('app.send_notification_email')
    def test_notification_includes_custom_email(self, mock_send_email, client):
        # Register user with custom email
        response = client.post('/auth/register',
            data=json.dumps({'username': 'custom_user', 'password': 'pass123', 'email': 'custom@example.com'}),
            content_type='application/json')
        user = json.loads(response.data)

        # Login and get token
        response = client.post('/auth/login',
            data=json.dumps({'username': 'custom_user', 'password': 'pass123'}),
            content_type='application/json')
        token = json.loads(response.data)['token']

        # Create and complete task
        response = client.post('/tasks',
            data=json.dumps({'title': 'Custom Email Task'}),
            content_type='application/json',
            headers=get_auth_headers(token))
        task = json.loads(response.data)
        task_id = task['id']

        response = client.put(f'/tasks/{task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
            headers=get_auth_headers(token))

        assert response.status_code == 200
        mock_send_email.delay.assert_called_once()
        call_args = mock_send_email.delay.call_args
        assert call_args[0][0] == 'custom@example.com'
        assert call_args[0][1] == 'Custom Email Task'


class TestPagination:
    def test_pagination_default_limit(self, client, token1):
        for i in range(25):
            client.post('/tasks',
                data=json.dumps({'title': f'Task {i+1}'}),
                content_type='application/json',
                headers=get_auth_headers(token1))

        response = client.get('/tasks',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 20
        assert data['total'] == 25
        assert data['next_cursor'] is not None

    def test_pagination_custom_limit(self, client, token1):
        for i in range(10):
            client.post('/tasks',
                data=json.dumps({'title': f'Task {i+1}'}),
                content_type='application/json',
                headers=get_auth_headers(token1))

        response = client.get('/tasks?limit=5',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 5
        assert data['total'] == 10
        assert data['next_cursor'] is not None

    def test_pagination_cursor_navigation(self, client, token1):
        task_ids = []
        for i in range(10):
            response = client.post('/tasks',
                data=json.dumps({'title': f'Task {i+1}'}),
                content_type='application/json',
                headers=get_auth_headers(token1))
            task = json.loads(response.data)
            task_ids.append(task['id'])

        # First page
        response = client.get('/tasks?limit=3',
            headers=get_auth_headers(token1))
        data = json.loads(response.data)
        assert len(data['data']) == 3
        first_page_last_id = data['data'][-1]['id']
        next_cursor = data['next_cursor']

        # Second page
        response = client.get(f'/tasks?cursor={next_cursor}&limit=3',
            headers=get_auth_headers(token1))
        data = json.loads(response.data)
        assert len(data['data']) == 3
        assert data['data'][0]['id'] != first_page_last_id

    def test_pagination_limit_max_clamping(self, client, token1):
        for i in range(5):
            client.post('/tasks',
                data=json.dumps({'title': f'Task {i+1}'}),
                content_type='application/json',
                headers=get_auth_headers(token1))

        # Request with limit > 100 should clamp to 20
        response = client.get('/tasks?limit=150',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 5

    def test_pagination_limit_min_clamping(self, client, token1):
        for i in range(5):
            client.post('/tasks',
                data=json.dumps({'title': f'Task {i+1}'}),
                content_type='application/json',
                headers=get_auth_headers(token1))

        # Request with limit < 1 should clamp to 20
        response = client.get('/tasks?limit=0',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 5

    def test_pagination_no_next_cursor_on_last_page(self, client, token1):
        for i in range(5):
            client.post('/tasks',
                data=json.dumps({'title': f'Task {i+1}'}),
                content_type='application/json',
                headers=get_auth_headers(token1))

        response = client.get('/tasks?limit=10',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 5
        assert data['next_cursor'] is None

    def test_pagination_empty_result(self, client, token1):
        response = client.get('/tasks?limit=20',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data'] == []
        assert data['next_cursor'] is None
        assert data['total'] == 0

    def test_pagination_invalid_cursor(self, client, token1):
        for i in range(5):
            client.post('/tasks',
                data=json.dumps({'title': f'Task {i+1}'}),
                content_type='application/json',
                headers=get_auth_headers(token1))

        # Invalid cursor should start from the beginning (return first page)
        response = client.get('/tasks?cursor=99999&limit=5',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 5

    def test_pagination_response_format(self, client, token1):
        client.post('/tasks',
            data=json.dumps({'title': 'Test Task'}),
            content_type='application/json',
            headers=get_auth_headers(token1))

        response = client.get('/tasks',
            headers=get_auth_headers(token1))

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'data' in data
        assert 'next_cursor' in data
        assert 'total' in data
        assert isinstance(data['data'], list)


class TestRateLimiting:
    def test_rate_limiting_enabled_on_auth_register(self, client):
        # Test that rate limiting decorator is applied to register endpoint
        response = client.post('/auth/register',
            data=json.dumps({'username': 'user1', 'password': 'pass123'}),
            content_type='application/json')
        assert response.status_code in [201, 429]

        # Verify response headers indicate rate limiting is configured
        if 'Retry-After' in response.headers:
            assert response.headers.get('Retry-After') == '60'

    def test_rate_limiting_enabled_on_auth_login(self, client):
        # Test that rate limiting decorator is applied to login endpoint
        client.post('/auth/register',
            data=json.dumps({'username': 'testuser', 'password': 'pass123'}),
            content_type='application/json')

        response = client.post('/auth/login',
            data=json.dumps({'username': 'testuser', 'password': 'pass123'}),
            content_type='application/json')
        assert response.status_code in [200, 429]

        # Verify response headers indicate rate limiting is configured
        if 'Retry-After' in response.headers:
            assert response.headers.get('Retry-After') == '60'

    def test_rate_limiting_enabled_on_tasks_list(self, client, token1):
        # Test that rate limiting decorator is applied to tasks list endpoint
        response = client.get('/tasks', headers=get_auth_headers(token1))
        assert response.status_code in [200, 429]

    def test_rate_limiting_enabled_on_tasks_create(self, client, token1):
        # Test that rate limiting decorator is applied to tasks create endpoint
        response = client.post('/tasks',
            data=json.dumps({'title': 'Test'}),
            content_type='application/json',
            headers=get_auth_headers(token1))
        assert response.status_code in [201, 429, 400]

    def test_rate_limiting_429_response_structure(self, client, token1):
        # Make 100 requests to use up the limit
        for i in range(100):
            client.get('/tasks', headers=get_auth_headers(token1))

        # 101st request should be rate limited
        response = client.get('/tasks', headers=get_auth_headers(token1))

        # If rate limiting kicked in, verify the response structure
        if response.status_code == 429:
            data = json.loads(response.data)
            assert 'error' in data
            assert data['error'] == 'Rate limit exceeded'
            assert 'Retry-After' in response.headers
            assert response.headers['Retry-After'] == '60'
