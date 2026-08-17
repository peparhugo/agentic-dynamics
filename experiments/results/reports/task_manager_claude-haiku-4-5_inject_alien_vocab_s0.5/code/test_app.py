import pytest
import json
from datetime import datetime, timedelta
from app import create_app
from config import TestConfig
from models import db, User, Task, Category, Priority

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_token(client):
    response = client.post('/api/auth/register', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'testpass123'
    })
    data = json.loads(response.data)
    return data['access_token']

@pytest.fixture
def auth_headers(auth_token):
    return {'Authorization': f'Bearer {auth_token}'}

# Auth Tests

class TestAuth:
    def test_register_user(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'password123'
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'access_token' in data
        assert data['user']['username'] == 'newuser'
        assert data['user']['email'] == 'new@example.com'

    def test_register_duplicate_username(self, client, auth_token):
        response = client.post('/api/auth/register', json={
            'username': 'testuser',
            'email': 'another@example.com',
            'password': 'password123'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'already exists' in data['error']

    def test_register_duplicate_email(self, client, auth_token):
        response = client.post('/api/auth/register', json={
            'username': 'anotheruser',
            'email': 'test@example.com',
            'password': 'password123'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'already exists' in data['error']

    def test_register_missing_fields(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'newuser'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Missing required fields' in data['error']

    def test_login_success(self, client):
        client.post('/api/auth/register', json={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123'
        })

        response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'testpass123'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'access_token' in data
        assert data['user']['username'] == 'testuser'

    def test_login_invalid_credentials(self, client):
        client.post('/api/auth/register', json={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123'
        })

        response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid credentials' in data['error']

    def test_login_missing_fields(self, client):
        response = client.post('/api/auth/login', json={
            'username': 'testuser'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Missing' in data['error']

# Category Tests

class TestCategories:
    def test_create_category(self, client, auth_headers):
        response = client.post('/api/categories',
            headers=auth_headers,
            json={
                'name': 'Work',
                'description': 'Work related tasks'
            })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['name'] == 'Work'
        assert data['description'] == 'Work related tasks'

    def test_create_category_duplicate(self, client, auth_headers):
        client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work'
        })
        response = client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work'
        })
        assert response.status_code == 400

    def test_create_category_missing_name(self, client, auth_headers):
        response = client.post('/api/categories', headers=auth_headers, json={})
        assert response.status_code == 400

    def test_get_categories(self, client, auth_headers):
        for i in range(5):
            client.post('/api/categories', headers=auth_headers, json={
                'name': f'Category{i}'
            })

        response = client.get('/api/categories', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['categories']) == 5
        assert data['total'] == 5

    def test_get_categories_pagination(self, client, auth_headers):
        for i in range(15):
            client.post('/api/categories', headers=auth_headers, json={
                'name': f'Category{i}'
            })

        response = client.get('/api/categories?page=1&per_page=10', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['categories']) == 10
        assert data['pages'] == 2
        assert data['current_page'] == 1

    def test_get_category(self, client, auth_headers):
        post_response = client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work'
        })
        category_id = json.loads(post_response.data)['id']

        response = client.get(f'/api/categories/{category_id}', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == 'Work'

    def test_get_category_not_found(self, client, auth_headers):
        response = client.get('/api/categories/999', headers=auth_headers)
        assert response.status_code == 404

    def test_update_category(self, client, auth_headers):
        post_response = client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work'
        })
        category_id = json.loads(post_response.data)['id']

        response = client.put(f'/api/categories/{category_id}', headers=auth_headers, json={
            'name': 'Updated Work',
            'description': 'Updated description'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == 'Updated Work'
        assert data['description'] == 'Updated description'

    def test_delete_category(self, client, auth_headers):
        post_response = client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work'
        })
        category_id = json.loads(post_response.data)['id']

        response = client.delete(f'/api/categories/{category_id}', headers=auth_headers)
        assert response.status_code == 200

        get_response = client.get(f'/api/categories/{category_id}', headers=auth_headers)
        assert get_response.status_code == 404

# Priority Tests

class TestPriorities:
    def test_create_priority(self, client, auth_headers):
        response = client.post('/api/priorities', headers=auth_headers, json={
            'name': 'High',
            'level': 1
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['name'] == 'High'
        assert data['level'] == 1

    def test_create_priority_duplicate(self, client, auth_headers):
        client.post('/api/priorities', headers=auth_headers, json={
            'name': 'High',
            'level': 1
        })
        response = client.post('/api/priorities', headers=auth_headers, json={
            'name': 'High',
            'level': 2
        })
        assert response.status_code == 400

    def test_get_priorities(self, client, auth_headers):
        for i in range(3):
            client.post('/api/priorities', headers=auth_headers, json={
                'name': f'Priority{i}',
                'level': i
            })

        response = client.get('/api/priorities', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['priorities']) == 3

    def test_get_priorities_ordered(self, client, auth_headers):
        client.post('/api/priorities', headers=auth_headers, json={
            'name': 'Low',
            'level': 3
        })
        client.post('/api/priorities', headers=auth_headers, json={
            'name': 'High',
            'level': 1
        })
        client.post('/api/priorities', headers=auth_headers, json={
            'name': 'Medium',
            'level': 2
        })

        response = client.get('/api/priorities', headers=auth_headers)
        data = json.loads(response.data)
        priorities = data['priorities']
        assert priorities[0]['level'] == 1
        assert priorities[1]['level'] == 2
        assert priorities[2]['level'] == 3

# Task Tests

class TestTasks:
    def test_create_task(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Test Task',
            'description': 'This is a test task',
            'status': 'pending'
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['title'] == 'Test Task'
        assert data['status'] == 'pending'

    def test_create_task_with_category_priority(self, client, auth_headers):
        cat_response = client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work'
        })
        category_id = json.loads(cat_response.data)['id']

        pri_response = client.post('/api/priorities', headers=auth_headers, json={
            'name': 'High',
            'level': 1
        })
        priority_id = json.loads(pri_response.data)['id']

        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Test Task',
            'description': 'This is a test task',
            'status': 'pending',
            'category_id': category_id,
            'priority_id': priority_id
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['category']['name'] == 'Work'
        assert data['priority']['name'] == 'High'

    def test_create_task_with_due_date(self, client, auth_headers):
        due_date = (datetime.utcnow() + timedelta(days=5)).isoformat()
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Test Task',
            'due_date': due_date
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['due_date'] is not None

    def test_create_task_invalid_due_date(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Test Task',
            'due_date': 'invalid-date'
        })
        assert response.status_code == 400

    def test_create_task_missing_title(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'description': 'No title'
        })
        assert response.status_code == 400

    def test_get_tasks(self, client, auth_headers):
        for i in range(5):
            client.post('/api/tasks', headers=auth_headers, json={
                'title': f'Task {i}'
            })

        response = client.get('/api/tasks', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['tasks']) == 5
        assert data['total'] == 5

    def test_get_tasks_pagination(self, client, auth_headers):
        for i in range(15):
            client.post('/api/tasks', headers=auth_headers, json={
                'title': f'Task {i}'
            })

        response = client.get('/api/tasks?page=2&per_page=5', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['tasks']) == 5
        assert data['current_page'] == 2

    def test_get_task(self, client, auth_headers):
        post_response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Test Task'
        })
        task_id = json.loads(post_response.data)['id']

        response = client.get(f'/api/tasks/{task_id}', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Test Task'

    def test_get_task_not_found(self, client, auth_headers):
        response = client.get('/api/tasks/999', headers=auth_headers)
        assert response.status_code == 404

    def test_update_task(self, client, auth_headers):
        post_response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Test Task',
            'status': 'pending'
        })
        task_id = json.loads(post_response.data)['id']

        response = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'title': 'Updated Task',
            'status': 'completed'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Updated Task'
        assert data['status'] == 'completed'

    def test_update_task_due_date(self, client, auth_headers):
        post_response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Test Task'
        })
        task_id = json.loads(post_response.data)['id']

        due_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
        response = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'due_date': due_date
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['due_date'] is not None

    def test_update_task_invalid_due_date(self, client, auth_headers):
        post_response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Test Task'
        })
        task_id = json.loads(post_response.data)['id']

        response = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'due_date': 'bad-date'
        })
        assert response.status_code == 400

    def test_delete_task(self, client, auth_headers):
        post_response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Test Task'
        })
        task_id = json.loads(post_response.data)['id']

        response = client.delete(f'/api/tasks/{task_id}', headers=auth_headers)
        assert response.status_code == 200

        get_response = client.get(f'/api/tasks/{task_id}', headers=auth_headers)
        assert get_response.status_code == 404

    def test_filter_tasks_by_status(self, client, auth_headers):
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task 1',
            'status': 'pending'
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task 2',
            'status': 'completed'
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task 3',
            'status': 'pending'
        })

        response = client.get('/api/tasks?status=pending', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['tasks']) == 2
        for task in data['tasks']:
            assert task['status'] == 'pending'

    def test_filter_tasks_by_category(self, client, auth_headers):
        cat_response = client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work'
        })
        category_id = json.loads(cat_response.data)['id']

        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Work Task',
            'category_id': category_id
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Personal Task'
        })

        response = client.get(f'/api/tasks?category_id={category_id}', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['tasks']) == 1
        assert data['tasks'][0]['title'] == 'Work Task'

    def test_filter_tasks_by_priority(self, client, auth_headers):
        pri_response = client.post('/api/priorities', headers=auth_headers, json={
            'name': 'High',
            'level': 1
        })
        priority_id = json.loads(pri_response.data)['id']

        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'High Priority Task',
            'priority_id': priority_id
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Low Priority Task'
        })

        response = client.get(f'/api/tasks?priority_id={priority_id}', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['tasks']) == 1
        assert data['tasks'][0]['title'] == 'High Priority Task'

    def test_search_tasks(self, client, auth_headers):
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Buy groceries',
            'description': 'Shopping'
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Project Alpha',
            'description': 'Development work'
        })

        response = client.get('/api/tasks?search=groceries', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['tasks']) == 1
        assert 'groceries' in data['tasks'][0]['title'].lower()

    def test_search_tasks_in_description(self, client, auth_headers):
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task 1',
            'description': 'This is about shopping'
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task 2',
            'description': 'This is about coding'
        })

        response = client.get('/api/tasks?search=shopping', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['tasks']) == 1

    def test_filter_tasks_by_assigned_user(self, client, auth_headers):
        reg_response = client.post('/api/auth/register', json={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'password123'
        })
        user_id = json.loads(reg_response.data)['user']['id']

        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task for User2',
            'assigned_to': user_id
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Unassigned Task'
        })

        response = client.get(f'/api/tasks?assigned_to={user_id}', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['tasks']) == 1
        assert data['tasks'][0]['assigned_to'] == user_id

    def test_multiple_filters(self, client, auth_headers):
        cat_response = client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work'
        })
        category_id = json.loads(cat_response.data)['id']

        pri_response = client.post('/api/priorities', headers=auth_headers, json={
            'name': 'High',
            'level': 1
        })
        priority_id = json.loads(pri_response.data)['id']

        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'High Work Task',
            'status': 'pending',
            'category_id': category_id,
            'priority_id': priority_id
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'High Personal Task',
            'status': 'pending',
            'priority_id': priority_id
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Low Work Task',
            'status': 'pending',
            'category_id': category_id
        })

        response = client.get(
            f'/api/tasks?status=pending&category_id={category_id}&priority_id={priority_id}',
            headers=auth_headers
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['tasks']) == 1
        assert data['tasks'][0]['title'] == 'High Work Task'

# User Tests

class TestUsers:
    def test_get_user(self, client, auth_headers):
        reg_response = client.post('/api/auth/register', json={
            'username': 'testuser2',
            'email': 'test2@example.com',
            'password': 'password123'
        })
        user_id = json.loads(reg_response.data)['user']['id']

        response = client.get(f'/api/users/{user_id}', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['username'] == 'testuser2'
        assert data['email'] == 'test2@example.com'

    def test_get_user_not_found(self, client, auth_headers):
        response = client.get('/api/users/999', headers=auth_headers)
        assert response.status_code == 404

    def test_get_all_users(self, client, auth_headers):
        client.post('/api/auth/register', json={
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'password123'
        })
        client.post('/api/auth/register', json={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'password123'
        })

        response = client.get('/api/users', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['users']) >= 2

    def test_get_users_pagination(self, client, auth_headers):
        for i in range(15):
            client.post('/api/auth/register', json={
                'username': f'user{i}',
                'email': f'user{i}@example.com',
                'password': 'password123'
            })

        response = client.get('/api/users?page=1&per_page=10', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['users']) == 10

# JWT Protection Tests

class TestJWTProtection:
    def test_access_protected_route_without_token(self, client):
        response = client.get('/api/tasks')
        assert response.status_code == 401

    def test_access_protected_route_with_invalid_token(self, client):
        response = client.get('/api/tasks', headers={
            'Authorization': 'Bearer invalid.token.here'
        })
        assert response.status_code == 422

    def test_create_category_without_token(self, client):
        response = client.post('/api/categories', json={
            'name': 'Work'
        })
        assert response.status_code == 401

    def test_create_task_without_token(self, client):
        response = client.post('/api/tasks', json={
            'title': 'Test'
        })
        assert response.status_code == 401
