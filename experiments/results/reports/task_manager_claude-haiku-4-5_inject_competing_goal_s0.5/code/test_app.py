import pytest
import json
from datetime import datetime, timedelta
from app import create_app
from models import db, User, Task, Category, Priority, TaskStatus

@pytest.fixture
def app():
    app = create_app('testing')

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

class TestAuth:
    def test_register_success(self, client):
        response = client.post('/auth/register', json={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        assert response.status_code == 201
        assert response.json['user']['username'] == 'testuser'
        assert response.json['user']['email'] == 'test@example.com'

    def test_register_missing_fields(self, client):
        response = client.post('/auth/register', json={
            'username': 'testuser'
        })
        assert response.status_code == 400
        assert 'Missing required fields' in response.json['error']

    def test_register_weak_password(self, client):
        response = client.post('/auth/register', json={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': '123'
        })
        assert response.status_code == 400
        assert 'at least 6 characters' in response.json['error']

    def test_register_duplicate_username(self, client):
        client.post('/auth/register', json={
            'username': 'testuser',
            'email': 'test1@example.com',
            'password': 'testpass123'
        })
        response = client.post('/auth/register', json={
            'username': 'testuser',
            'email': 'test2@example.com',
            'password': 'testpass123'
        })
        assert response.status_code == 409
        assert 'Username already exists' in response.json['error']

    def test_register_duplicate_email(self, client):
        client.post('/auth/register', json={
            'username': 'testuser1',
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        response = client.post('/auth/register', json={
            'username': 'testuser2',
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        assert response.status_code == 409
        assert 'Email already exists' in response.json['error']

    def test_login_success(self, client):
        client.post('/auth/register', json={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        response = client.post('/auth/login', json={
            'username': 'testuser',
            'password': 'testpass123'
        })
        assert response.status_code == 200
        assert 'token' in response.json
        assert response.json['user']['username'] == 'testuser'

    def test_login_invalid_username(self, client):
        response = client.post('/auth/login', json={
            'username': 'nonexistent',
            'password': 'testpass123'
        })
        assert response.status_code == 401
        assert 'Invalid username or password' in response.json['error']

    def test_login_invalid_password(self, client):
        client.post('/auth/register', json={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        response = client.post('/auth/login', json={
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        assert response.status_code == 401
        assert 'Invalid username or password' in response.json['error']

    def test_login_missing_fields(self, client):
        response = client.post('/auth/login', json={
            'username': 'testuser'
        })
        assert response.status_code == 400
        assert 'Missing username or password' in response.json['error']

@pytest.fixture
def auth_token(client):
    client.post('/auth/register', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'testpass123'
    })
    response = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'testpass123'
    })
    return response.json['token']

@pytest.fixture
def user_id(client):
    response = client.post('/auth/register', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'testpass123'
    })
    return response.json['user']['id']

class TestTaskCRUD:
    def test_create_task_success(self, client, auth_token):
        response = client.post('/tasks',
            json={'title': 'Test Task'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['task']['title'] == 'Test Task'
        assert response.json['task']['status'] == 'todo'

    def test_create_task_missing_title(self, client, auth_token):
        response = client.post('/tasks',
            json={},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400
        assert 'Title is required' in response.json['error']

    def test_create_task_with_description(self, client, auth_token):
        response = client.post('/tasks',
            json={
                'title': 'Test Task',
                'description': 'Task description'
            },
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['task']['description'] == 'Task description'

    def test_create_task_with_status(self, client, auth_token):
        response = client.post('/tasks',
            json={
                'title': 'Test Task',
                'status': 'in_progress'
            },
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['task']['status'] == 'in_progress'

    def test_create_task_with_due_date(self, client, auth_token):
        due_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
        response = client.post('/tasks',
            json={
                'title': 'Test Task',
                'due_date': due_date
            },
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['task']['due_date'] is not None

    def test_create_task_invalid_due_date(self, client, auth_token):
        response = client.post('/tasks',
            json={
                'title': 'Test Task',
                'due_date': 'invalid-date'
            },
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400
        assert 'Invalid due_date format' in response.json['error']

    def test_get_task(self, client, auth_token):
        create_response = client.post('/tasks',
            json={'title': 'Test Task'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        task_id = create_response.json['task']['id']

        response = client.get(f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['title'] == 'Test Task'

    def test_get_nonexistent_task(self, client, auth_token):
        response = client.get('/tasks/999',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404
        assert 'Task not found' in response.json['error']

    def test_update_task(self, client, auth_token):
        create_response = client.post('/tasks',
            json={'title': 'Original Title'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        task_id = create_response.json['task']['id']

        response = client.put(f'/tasks/{task_id}',
            json={'title': 'Updated Title', 'status': 'completed'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['task']['title'] == 'Updated Title'
        assert response.json['task']['status'] == 'completed'

    def test_update_task_description(self, client, auth_token):
        create_response = client.post('/tasks',
            json={'title': 'Test Task'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        task_id = create_response.json['task']['id']

        response = client.put(f'/tasks/{task_id}',
            json={'description': 'New description'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['task']['description'] == 'New description'

    def test_update_task_invalid_status(self, client, auth_token):
        create_response = client.post('/tasks',
            json={'title': 'Test Task'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        task_id = create_response.json['task']['id']

        response = client.put(f'/tasks/{task_id}',
            json={'status': 'invalid_status'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400
        assert 'Invalid status' in response.json['error']

    def test_update_nonexistent_task(self, client, auth_token):
        response = client.put('/tasks/999',
            json={'title': 'Updated'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404
        assert 'Task not found' in response.json['error']

    def test_delete_task(self, client, auth_token):
        create_response = client.post('/tasks',
            json={'title': 'Test Task'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        task_id = create_response.json['task']['id']

        response = client.delete(f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert 'deleted successfully' in response.json['message']

        get_response = client.get(f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert get_response.status_code == 404

    def test_delete_nonexistent_task(self, client, auth_token):
        response = client.delete('/tasks/999',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404

class TestTaskFiltering:
    def test_get_tasks_paginated(self, client, auth_token):
        for i in range(15):
            client.post('/tasks',
                json={'title': f'Task {i}'},
                headers={'Authorization': f'Bearer {auth_token}'}
            )

        response = client.get('/tasks?page=1&per_page=5',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 5
        assert response.json['pagination']['total'] == 15
        assert response.json['pagination']['pages'] == 3

    def test_get_tasks_page_limit(self, client, auth_token):
        for i in range(20):
            client.post('/tasks',
                json={'title': f'Task {i}'},
                headers={'Authorization': f'Bearer {auth_token}'}
            )

        response = client.get('/tasks?page=1&per_page=200',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['pagination']['per_page'] == 100

    def test_filter_by_status(self, client, auth_token):
        client.post('/tasks',
            json={'title': 'Task 1', 'status': 'todo'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        client.post('/tasks',
            json={'title': 'Task 2', 'status': 'in_progress'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        client.post('/tasks',
            json={'title': 'Task 3', 'status': 'completed'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        response = client.get('/tasks?status=completed',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert response.json['tasks'][0]['status'] == 'completed'

    def test_filter_by_invalid_status(self, client, auth_token):
        response = client.get('/tasks?status=invalid',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400

    def test_search_by_title(self, client, auth_token):
        client.post('/tasks',
            json={'title': 'Buy groceries'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        client.post('/tasks',
            json={'title': 'Fix bug in login'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        response = client.get('/tasks?search=groceries',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert 'groceries' in response.json['tasks'][0]['title'].lower()

    def test_search_by_description(self, client, auth_token):
        client.post('/tasks',
            json={
                'title': 'Task 1',
                'description': 'Important meeting with client'
            },
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        client.post('/tasks',
            json={
                'title': 'Task 2',
                'description': 'Regular standup meeting'
            },
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        response = client.get('/tasks?search=client',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert 'client' in response.json['tasks'][0]['description'].lower()

class TestCategories:
    def test_create_category(self, client, auth_token):
        response = client.post('/tasks/categories',
            json={'name': 'Work'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['category']['name'] == 'Work'

    def test_create_duplicate_category(self, client, auth_token):
        client.post('/tasks/categories',
            json={'name': 'Work'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        response = client.post('/tasks/categories',
            json={'name': 'Work'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 409

    def test_get_categories(self, client, auth_token):
        client.post('/tasks/categories',
            json={'name': 'Work'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        client.post('/tasks/categories',
            json={'name': 'Personal'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        response = client.get('/tasks/categories',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json) == 2

    def test_update_category(self, client, auth_token):
        create_response = client.post('/tasks/categories',
            json={'name': 'Work'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        cat_id = create_response.json['category']['id']

        response = client.put(f'/tasks/categories/{cat_id}',
            json={'name': 'Job'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['category']['name'] == 'Job'

    def test_delete_category(self, client, auth_token):
        create_response = client.post('/tasks/categories',
            json={'name': 'Work'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        cat_id = create_response.json['category']['id']

        response = client.delete(f'/tasks/categories/{cat_id}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200

        get_response = client.get('/tasks/categories',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert len(get_response.json) == 0

    def test_create_task_with_category(self, client, auth_token):
        cat_response = client.post('/tasks/categories',
            json={'name': 'Work'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        cat_id = cat_response.json['category']['id']

        response = client.post('/tasks',
            json={'title': 'Task', 'category_id': cat_id},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['task']['category']['name'] == 'Work'

    def test_filter_by_category(self, client, auth_token):
        cat_response = client.post('/tasks/categories',
            json={'name': 'Work'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        cat_id = cat_response.json['category']['id']

        client.post('/tasks',
            json={'title': 'Work Task', 'category_id': cat_id},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        client.post('/tasks',
            json={'title': 'Personal Task'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        response = client.get(f'/tasks?category_id={cat_id}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert response.json['tasks'][0]['title'] == 'Work Task'

class TestPriorities:
    def test_get_priorities(self, client):
        response = client.get('/tasks/priorities')
        assert response.status_code == 200
        assert len(response.json) == 4
        assert response.json[0]['name'] == 'Low'
        assert response.json[3]['name'] == 'Critical'

    def test_create_task_with_priority(self, client, auth_token):
        response = client.post('/tasks',
            json={'title': 'Urgent Task', 'priority_id': 4},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['task']['priority']['name'] == 'Critical'

    def test_filter_by_priority(self, client, auth_token):
        client.post('/tasks',
            json={'title': 'Low Priority', 'priority_id': 1},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        client.post('/tasks',
            json={'title': 'High Priority', 'priority_id': 3},
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        response = client.get('/tasks?priority_id=3',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert response.json['tasks'][0]['priority']['name'] == 'High'

class TestTaskAssignment:
    def test_create_task_assigned_to_user(self, client, auth_token):
        register_response = client.post('/auth/register', json={
            'username': 'other_user',
            'email': 'other@example.com',
            'password': 'testpass123'
        })
        other_user_id = register_response.json['user']['id']

        response = client.post('/tasks',
            json={'title': 'Task', 'assigned_to': other_user_id},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['task']['assigned_to'] == other_user_id

    def test_assign_to_nonexistent_user(self, client, auth_token):
        response = client.post('/tasks',
            json={'title': 'Task', 'assigned_to': 999},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404
        assert 'Assigned user not found' in response.json['error']

    def test_filter_by_assigned_to(self, client, auth_token):
        register_response = client.post('/auth/register', json={
            'username': 'other_user',
            'email': 'other@example.com',
            'password': 'testpass123'
        })
        other_user_id = register_response.json['user']['id']

        client.post('/tasks',
            json={'title': 'Task 1', 'assigned_to': other_user_id},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        client.post('/tasks',
            json={'title': 'Task 2'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        response = client.get(f'/tasks?assigned_to={other_user_id}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert response.json['tasks'][0]['assigned_to'] == other_user_id

class TestAuthentication:
    def test_request_without_token(self, client):
        response = client.get('/tasks')
        assert response.status_code == 401
        assert 'Token is missing' in response.json['error']

    def test_request_with_invalid_token(self, client):
        response = client.get('/tasks',
            headers={'Authorization': 'Bearer invalid_token'}
        )
        assert response.status_code == 401
        assert 'Invalid token' in response.json['error']

    def test_request_with_malformed_auth_header(self, client):
        response = client.get('/tasks',
            headers={'Authorization': 'InvalidFormat'}
        )
        assert response.status_code == 401
        assert 'Invalid token format' in response.json['error']

class TestTaskIsolation:
    def test_user_can_only_see_own_tasks(self, client):
        user1_response = client.post('/auth/register', json={
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'testpass123'
        })
        user1_id = user1_response.json['user']['id']

        user1_token = client.post('/auth/login', json={
            'username': 'user1',
            'password': 'testpass123'
        }).json['token']

        user2_response = client.post('/auth/register', json={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'testpass123'
        })
        user2_id = user2_response.json['user']['id']

        user2_token = client.post('/auth/login', json={
            'username': 'user2',
            'password': 'testpass123'
        }).json['token']

        client.post('/tasks',
            json={'title': 'User 1 Task'},
            headers={'Authorization': f'Bearer {user1_token}'}
        )

        client.post('/tasks',
            json={'title': 'User 2 Task'},
            headers={'Authorization': f'Bearer {user2_token}'}
        )

        user1_tasks = client.get('/tasks',
            headers={'Authorization': f'Bearer {user1_token}'}
        ).json['tasks']

        user2_tasks = client.get('/tasks',
            headers={'Authorization': f'Bearer {user2_token}'}
        ).json['tasks']

        assert len(user1_tasks) == 1
        assert user1_tasks[0]['title'] == 'User 1 Task'

        assert len(user2_tasks) == 1
        assert user2_tasks[0]['title'] == 'User 2 Task'

    def test_user_cannot_modify_others_tasks(self, client):
        user1_token = client.post('/auth/login', json={
            'username': 'user1',
            'password': 'testpass123'
        }).json['token'] if False else None

        user1_response = client.post('/auth/register', json={
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'testpass123'
        })
        user1_token = client.post('/auth/login', json={
            'username': 'user1',
            'password': 'testpass123'
        }).json['token']

        user2_response = client.post('/auth/register', json={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'testpass123'
        })
        user2_token = client.post('/auth/login', json={
            'username': 'user2',
            'password': 'testpass123'
        }).json['token']

        task_response = client.post('/tasks',
            json={'title': 'User 1 Task'},
            headers={'Authorization': f'Bearer {user1_token}'}
        )
        task_id = task_response.json['task']['id']

        response = client.put(f'/tasks/{task_id}',
            json={'title': 'Hacked Task'},
            headers={'Authorization': f'Bearer {user2_token}'}
        )
        assert response.status_code == 404

class TestHealthCheck:
    def test_health_endpoint(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json['status'] == 'healthy'
