import pytest
import json
from datetime import datetime, timedelta
from app import create_app
from models import db, User, Task, Category
from config import TestConfig

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
def auth_headers(client):
    client.post('/api/auth/register', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'testpass123'
    })
    response = client.post('/api/auth/login', json={
        'username': 'testuser',
        'password': 'testpass123'
    })
    token = response.json['access_token']
    return {'Authorization': f'Bearer {token}'}

@pytest.fixture
def second_user_headers(client):
    client.post('/api/auth/register', json={
        'username': 'seconduser',
        'email': 'second@example.com',
        'password': 'testpass123'
    })
    response = client.post('/api/auth/login', json={
        'username': 'seconduser',
        'password': 'testpass123'
    })
    token = response.json['access_token']
    return {'Authorization': f'Bearer {token}'}

# === AUTH TESTS ===

class TestAuth:
    def test_register_success(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'password123'
        })
        assert response.status_code == 201
        assert response.json['user']['username'] == 'newuser'
        assert response.json['user']['email'] == 'newuser@example.com'

    def test_register_missing_fields(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'newuser'
        })
        assert response.status_code == 400
        assert 'Missing required fields' in response.json['error']

    def test_register_duplicate_username(self, client, auth_headers):
        response = client.post('/api/auth/register', json={
            'username': 'testuser',
            'email': 'another@example.com',
            'password': 'password123'
        })
        assert response.status_code == 409
        assert 'Username already exists' in response.json['error']

    def test_register_duplicate_email(self, client, auth_headers):
        response = client.post('/api/auth/register', json={
            'username': 'anotheruser',
            'email': 'test@example.com',
            'password': 'password123'
        })
        assert response.status_code == 409
        assert 'Email already exists' in response.json['error']

    def test_login_success(self, client):
        client.post('/api/auth/register', json={
            'username': 'user',
            'email': 'user@example.com',
            'password': 'pass123'
        })
        response = client.post('/api/auth/login', json={
            'username': 'user',
            'password': 'pass123'
        })
        assert response.status_code == 200
        assert 'access_token' in response.json
        assert response.json['user']['username'] == 'user'

    def test_login_wrong_password(self, client, auth_headers):
        response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        assert response.status_code == 401
        assert 'Invalid username or password' in response.json['error']

    def test_login_nonexistent_user(self, client):
        response = client.post('/api/auth/login', json={
            'username': 'nonexistent',
            'password': 'pass123'
        })
        assert response.status_code == 401
        assert 'Invalid username or password' in response.json['error']

    def test_login_missing_fields(self, client):
        response = client.post('/api/auth/login', json={
            'username': 'user'
        })
        assert response.status_code == 400
        assert 'Missing username or password' in response.json['error']

# === USER TESTS ===

class TestUsers:
    def test_get_user_success(self, client, auth_headers):
        response = client.get('/api/users/1', headers=auth_headers)
        assert response.status_code == 200
        assert response.json['username'] == 'testuser'

    def test_get_user_not_found(self, client, auth_headers):
        response = client.get('/api/users/999', headers=auth_headers)
        assert response.status_code == 404
        assert 'User not found' in response.json['error']

    def test_get_user_without_auth(self, client):
        response = client.get('/api/users/1')
        assert response.status_code == 401

    def test_update_user_success(self, client, auth_headers):
        response = client.put('/api/users/1', headers=auth_headers, json={
            'email': 'newemail@example.com'
        })
        assert response.status_code == 200
        assert response.json['email'] == 'newemail@example.com'

    def test_update_user_password(self, client, auth_headers):
        response = client.put('/api/users/1', headers=auth_headers, json={
            'password': 'newpassword123'
        })
        assert response.status_code == 200

        login_response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'newpassword123'
        })
        assert login_response.status_code == 200

    def test_update_user_duplicate_email(self, client, auth_headers, second_user_headers):
        response = client.put('/api/users/1', headers=auth_headers, json={
            'email': 'second@example.com'
        })
        assert response.status_code == 409
        assert 'Email already in use' in response.json['error']

    def test_update_user_unauthorized(self, client, auth_headers, second_user_headers):
        response = client.put('/api/users/2', headers=auth_headers, json={
            'email': 'newemail@example.com'
        })
        assert response.status_code == 401
        assert 'Unauthorized' in response.json['error']

    def test_update_nonexistent_user(self, client, auth_headers):
        response = client.put('/api/users/999', headers=auth_headers, json={
            'email': 'newemail@example.com'
        })
        assert response.status_code == 404
        assert 'User not found' in response.json['error']

# === CATEGORY TESTS ===

class TestCategories:
    def test_create_category_success(self, client, auth_headers):
        response = client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work',
            'description': 'Work-related tasks'
        })
        assert response.status_code == 201
        assert response.json['name'] == 'Work'
        assert response.json['description'] == 'Work-related tasks'

    def test_create_category_missing_name(self, client, auth_headers):
        response = client.post('/api/categories', headers=auth_headers, json={
            'description': 'Some tasks'
        })
        assert response.status_code == 400
        assert 'Missing required fields' in response.json['error']

    def test_create_duplicate_category(self, client, auth_headers):
        client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work'
        })
        response = client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work'
        })
        assert response.status_code == 409
        assert 'Category already exists' in response.json['error']

    def test_get_categories(self, client, auth_headers):
        client.post('/api/categories', headers=auth_headers, json={'name': 'Work'})
        client.post('/api/categories', headers=auth_headers, json={'name': 'Personal'})
        response = client.get('/api/categories', headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json) == 2

    def test_get_category_success(self, client, auth_headers):
        create_resp = client.post('/api/categories', headers=auth_headers, json={'name': 'Work'})
        cat_id = create_resp.json['id']
        response = client.get(f'/api/categories/{cat_id}', headers=auth_headers)
        assert response.status_code == 200
        assert response.json['name'] == 'Work'

    def test_get_category_not_found(self, client, auth_headers):
        response = client.get('/api/categories/999', headers=auth_headers)
        assert response.status_code == 404
        assert 'Category not found' in response.json['error']

    def test_update_category_success(self, client, auth_headers):
        create_resp = client.post('/api/categories', headers=auth_headers, json={'name': 'Work'})
        cat_id = create_resp.json['id']
        response = client.put(f'/api/categories/{cat_id}', headers=auth_headers, json={
            'name': 'Updated Work',
            'description': 'New description'
        })
        assert response.status_code == 200
        assert response.json['name'] == 'Updated Work'
        assert response.json['description'] == 'New description'

    def test_update_category_duplicate_name(self, client, auth_headers):
        client.post('/api/categories', headers=auth_headers, json={'name': 'Work'})
        create_resp = client.post('/api/categories', headers=auth_headers, json={'name': 'Personal'})
        cat_id = create_resp.json['id']
        response = client.put(f'/api/categories/{cat_id}', headers=auth_headers, json={
            'name': 'Work'
        })
        assert response.status_code == 409
        assert 'Category name already in use' in response.json['error']

    def test_delete_category_success(self, client, auth_headers):
        create_resp = client.post('/api/categories', headers=auth_headers, json={'name': 'Work'})
        cat_id = create_resp.json['id']
        response = client.delete(f'/api/categories/{cat_id}', headers=auth_headers)
        assert response.status_code == 200
        assert 'Category deleted successfully' in response.json['message']

        get_resp = client.get(f'/api/categories/{cat_id}', headers=auth_headers)
        assert get_resp.status_code == 404

    def test_delete_category_not_found(self, client, auth_headers):
        response = client.delete('/api/categories/999', headers=auth_headers)
        assert response.status_code == 404
        assert 'Category not found' in response.json['error']

# === TASK TESTS ===

class TestTasks:
    def test_create_task_success(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Complete project',
            'description': 'Finish the API',
            'priority': 'high',
            'status': 'pending'
        })
        assert response.status_code == 201
        assert response.json['title'] == 'Complete project'
        assert response.json['priority'] == 'high'

    def test_create_task_missing_title(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'description': 'Some task'
        })
        assert response.status_code == 400
        assert 'Missing required fields' in response.json['error']

    def test_create_task_invalid_status(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'status': 'invalid_status'
        })
        assert response.status_code == 400
        assert 'Invalid status' in response.json['error']

    def test_create_task_invalid_priority(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'priority': 'invalid_priority'
        })
        assert response.status_code == 400
        assert 'Invalid priority' in response.json['error']

    def test_create_task_with_category(self, client, auth_headers):
        cat_resp = client.post('/api/categories', headers=auth_headers, json={'name': 'Work'})
        cat_id = cat_resp.json['id']
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'category_id': cat_id
        })
        assert response.status_code == 201
        assert response.json['category']['id'] == cat_id

    def test_create_task_invalid_category(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'category_id': 999
        })
        assert response.status_code == 404
        assert 'Category not found' in response.json['error']

    def test_create_task_with_assignment(self, client, auth_headers, second_user_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'assigned_to_id': 2
        })
        assert response.status_code == 201
        assert response.json['assigned_to']['id'] == 2

    def test_create_task_invalid_assignment(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'assigned_to_id': 999
        })
        assert response.status_code == 404
        assert 'User not found' in response.json['error']

    def test_create_task_with_due_date(self, client, auth_headers):
        due_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'due_date': due_date
        })
        assert response.status_code == 201
        assert response.json['due_date'] is not None

    def test_create_task_invalid_due_date(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'due_date': 'invalid-date'
        })
        assert response.status_code == 400
        assert 'Invalid due_date format' in response.json['error']

    def test_get_task_success(self, client, auth_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'My Task'
        })
        task_id = create_resp.json['id']
        response = client.get(f'/api/tasks/{task_id}', headers=auth_headers)
        assert response.status_code == 200
        assert response.json['title'] == 'My Task'

    def test_get_task_not_found(self, client, auth_headers):
        response = client.get('/api/tasks/999', headers=auth_headers)
        assert response.status_code == 404
        assert 'Task not found' in response.json['error']

    def test_get_task_unauthorized(self, client, auth_headers, second_user_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'My Task'
        })
        task_id = create_resp.json['id']
        response = client.get(f'/api/tasks/{task_id}', headers=second_user_headers)
        assert response.status_code == 401
        assert 'Unauthorized' in response.json['error']

    def test_get_task_assigned_to_user(self, client, auth_headers, second_user_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'My Task',
            'assigned_to_id': 2
        })
        task_id = create_resp.json['id']
        response = client.get(f'/api/tasks/{task_id}', headers=second_user_headers)
        assert response.status_code == 200
        assert response.json['title'] == 'My Task'

    def test_get_tasks_list(self, client, auth_headers):
        client.post('/api/tasks', headers=auth_headers, json={'title': 'Task 1'})
        client.post('/api/tasks', headers=auth_headers, json={'title': 'Task 2'})
        response = client.get('/api/tasks', headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json['tasks']) == 2

    def test_get_tasks_pagination(self, client, auth_headers):
        for i in range(15):
            client.post('/api/tasks', headers=auth_headers, json={'title': f'Task {i}'})
        response = client.get('/api/tasks?page=1&per_page=10', headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json['tasks']) == 10
        assert response.json['pagination']['total'] == 15
        assert response.json['pagination']['pages'] == 2

    def test_get_tasks_filter_by_status(self, client, auth_headers):
        client.post('/api/tasks', headers=auth_headers, json={'title': 'Task 1', 'status': 'pending'})
        client.post('/api/tasks', headers=auth_headers, json={'title': 'Task 2', 'status': 'completed'})
        response = client.get('/api/tasks?status=pending', headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert response.json['tasks'][0]['status'] == 'pending'

    def test_get_tasks_filter_invalid_status(self, client, auth_headers):
        response = client.get('/api/tasks?status=invalid', headers=auth_headers)
        assert response.status_code == 400
        assert 'Invalid status' in response.json['error']

    def test_get_tasks_filter_by_priority(self, client, auth_headers):
        client.post('/api/tasks', headers=auth_headers, json={'title': 'Task 1', 'priority': 'high'})
        client.post('/api/tasks', headers=auth_headers, json={'title': 'Task 2', 'priority': 'low'})
        response = client.get('/api/tasks?priority=high', headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert response.json['tasks'][0]['priority'] == 'high'

    def test_get_tasks_filter_invalid_priority(self, client, auth_headers):
        response = client.get('/api/tasks?priority=invalid', headers=auth_headers)
        assert response.status_code == 400
        assert 'Invalid priority' in response.json['error']

    def test_get_tasks_filter_by_category(self, client, auth_headers):
        cat_resp = client.post('/api/categories', headers=auth_headers, json={'name': 'Work'})
        cat_id = cat_resp.json['id']
        client.post('/api/tasks', headers=auth_headers, json={'title': 'Task 1', 'category_id': cat_id})
        client.post('/api/tasks', headers=auth_headers, json={'title': 'Task 2'})
        response = client.get(f'/api/tasks?category_id={cat_id}', headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1

    def test_get_tasks_search(self, client, auth_headers):
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Buy groceries',
            'description': 'Shopping for dinner'
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Write report',
            'description': 'Monthly report'
        })
        response = client.get('/api/tasks?search=groceries', headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1

    def test_update_task_success(self, client, auth_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Original Task'
        })
        task_id = create_resp.json['id']
        response = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'title': 'Updated Task',
            'status': 'completed'
        })
        assert response.status_code == 200
        assert response.json['title'] == 'Updated Task'
        assert response.json['status'] == 'completed'

    def test_update_task_invalid_status(self, client, auth_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task'
        })
        task_id = create_resp.json['id']
        response = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'status': 'invalid_status'
        })
        assert response.status_code == 400
        assert 'Invalid status' in response.json['error']

    def test_update_task_invalid_priority(self, client, auth_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task'
        })
        task_id = create_resp.json['id']
        response = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'priority': 'invalid_priority'
        })
        assert response.status_code == 400
        assert 'Invalid priority' in response.json['error']

    def test_update_task_unauthorized(self, client, auth_headers, second_user_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task'
        })
        task_id = create_resp.json['id']
        response = client.put(f'/api/tasks/{task_id}', headers=second_user_headers, json={
            'title': 'Updated'
        })
        assert response.status_code == 401
        assert 'Only task creator can update it' in response.json['error']

    def test_update_task_not_found(self, client, auth_headers):
        response = client.put('/api/tasks/999', headers=auth_headers, json={
            'title': 'Updated'
        })
        assert response.status_code == 404
        assert 'Task not found' in response.json['error']

    def test_update_task_category(self, client, auth_headers):
        cat_resp = client.post('/api/categories', headers=auth_headers, json={'name': 'Work'})
        cat_id = cat_resp.json['id']
        create_resp = client.post('/api/tasks', headers=auth_headers, json={'title': 'Task'})
        task_id = create_resp.json['id']
        response = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'category_id': cat_id
        })
        assert response.status_code == 200
        assert response.json['category']['id'] == cat_id

    def test_update_task_clear_category(self, client, auth_headers):
        cat_resp = client.post('/api/categories', headers=auth_headers, json={'name': 'Work'})
        cat_id = cat_resp.json['id']
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'category_id': cat_id
        })
        task_id = create_resp.json['id']
        response = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'category_id': None
        })
        assert response.status_code == 200
        assert response.json['category'] is None

    def test_update_task_assignment(self, client, auth_headers, second_user_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={'title': 'Task'})
        task_id = create_resp.json['id']
        response = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'assigned_to_id': 2
        })
        assert response.status_code == 200
        assert response.json['assigned_to']['id'] == 2

    def test_update_task_clear_assignment(self, client, auth_headers, second_user_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'assigned_to_id': 2
        })
        task_id = create_resp.json['id']
        response = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'assigned_to_id': None
        })
        assert response.status_code == 200
        assert response.json['assigned_to'] is None

    def test_delete_task_success(self, client, auth_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task'
        })
        task_id = create_resp.json['id']
        response = client.delete(f'/api/tasks/{task_id}', headers=auth_headers)
        assert response.status_code == 200
        assert 'Task deleted successfully' in response.json['message']

        get_resp = client.get(f'/api/tasks/{task_id}', headers=auth_headers)
        assert get_resp.status_code == 404

    def test_delete_task_unauthorized(self, client, auth_headers, second_user_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task'
        })
        task_id = create_resp.json['id']
        response = client.delete(f'/api/tasks/{task_id}', headers=second_user_headers)
        assert response.status_code == 401
        assert 'Only task creator can delete it' in response.json['error']

    def test_delete_task_not_found(self, client, auth_headers):
        response = client.delete('/api/tasks/999', headers=auth_headers)
        assert response.status_code == 404
        assert 'Task not found' in response.json['error']

# === INTEGRATION TESTS ===

class TestIntegration:
    def test_full_task_workflow(self, client, auth_headers):
        cat_resp = client.post('/api/categories', headers=auth_headers, json={
            'name': 'Work',
            'description': 'Work tasks'
        })
        cat_id = cat_resp.json['id']

        task_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Complete API',
            'description': 'Build task management API',
            'priority': 'high',
            'status': 'pending',
            'category_id': cat_id
        })
        task_id = task_resp.json['id']

        update_resp = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'status': 'in_progress'
        })
        assert update_resp.json['status'] == 'in_progress'

        complete_resp = client.put(f'/api/tasks/{task_id}', headers=auth_headers, json={
            'status': 'completed'
        })
        assert complete_resp.json['status'] == 'completed'

    def test_user_sees_assigned_tasks(self, client, auth_headers, second_user_headers):
        create_resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task for second user',
            'assigned_to_id': 2
        })
        task_id = create_resp.json['id']

        tasks_resp = client.get('/api/tasks', headers=second_user_headers)
        task_ids = [t['id'] for t in tasks_resp.json['tasks']]
        assert task_id in task_ids

    def test_complex_filtering(self, client, auth_headers):
        cat_resp = client.post('/api/categories', headers=auth_headers, json={'name': 'Work'})
        cat_id = cat_resp.json['id']

        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'High priority work task',
            'priority': 'high',
            'status': 'pending',
            'category_id': cat_id
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Low priority work task',
            'priority': 'low',
            'status': 'completed',
            'category_id': cat_id
        })
        client.post('/api/tasks', headers=auth_headers, json={
            'title': 'High priority personal task',
            'priority': 'high',
            'status': 'pending'
        })

        response = client.get(
            f'/api/tasks?category_id={cat_id}&priority=high&status=pending',
            headers=auth_headers
        )
        assert len(response.json['tasks']) == 1
        assert response.json['tasks'][0]['title'] == 'High priority work task'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
