import pytest
from datetime import datetime, timedelta
from app import create_app
from config import TestConfig
from models import db, User, Task, Category, Priority

@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def auth_header(client):
    client.post('/api/auth/register', json={
        'username': 'testuser1',
        'email': 'test1@example.com',
        'password': 'password123'
    })
    response = client.post('/api/auth/login', json={
        'username': 'testuser1',
        'password': 'password123'
    })
    token = response.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}

def get_user_by_username(client, username):
    with client.application.app_context():
        return User.query.filter_by(username=username).first().id

class TestAuth:
    def test_register_success(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'password123'
        })
        assert response.status_code == 201
        assert response.get_json()['user']['username'] == 'newuser'
        assert response.get_json()['user']['email'] == 'newuser@example.com'

    def test_register_missing_fields(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'newuser'
        })
        assert response.status_code == 400

    def test_register_duplicate_username(self, client, user1):
        response = client.post('/api/auth/register', json={
            'username': 'testuser1',
            'email': 'different@example.com',
            'password': 'password123'
        })
        assert response.status_code == 409
        assert 'already exists' in response.get_json()['message']

    def test_register_duplicate_email(self, client, user1):
        response = client.post('/api/auth/register', json={
            'username': 'differentuser',
            'email': 'test1@example.com',
            'password': 'password123'
        })
        assert response.status_code == 409
        assert 'already exists' in response.get_json()['message']

    def test_login_success(self, client, user1):
        response = client.post('/api/auth/login', json={
            'username': 'testuser1',
            'password': 'password123'
        })
        assert response.status_code == 200
        assert 'access_token' in response.get_json()
        assert response.get_json()['user']['username'] == 'testuser1'

    def test_login_invalid_password(self, client, user1):
        response = client.post('/api/auth/login', json={
            'username': 'testuser1',
            'password': 'wrongpassword'
        })
        assert response.status_code == 401

    def test_login_invalid_username(self, client):
        response = client.post('/api/auth/login', json={
            'username': 'nonexistent',
            'password': 'password123'
        })
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        response = client.post('/api/auth/login', json={
            'username': 'testuser1'
        })
        assert response.status_code == 400

    def test_get_current_user(self, client, auth_header):
        response = client.get('/api/auth/me', headers=auth_header)
        assert response.status_code == 200
        assert response.get_json()['username'] == 'testuser1'

    def test_get_current_user_unauthorized(self, client):
        response = client.get('/api/auth/me')
        assert response.status_code == 401

class TestTasks:
    def test_create_task_success(self, client, auth_header):
        response = client.post('/api/tasks', headers=auth_header, json={
            'title': 'Test Task',
            'description': 'This is a test task',
            'status': 'pending'
        })
        assert response.status_code == 201
        assert response.get_json()['task']['title'] == 'Test Task'
        assert response.get_json()['task']['status'] == 'pending'

    def test_create_task_with_due_date(self, client, auth_header):
        due_date = (datetime.utcnow() + timedelta(days=5)).isoformat()
        response = client.post('/api/tasks', headers=auth_header, json={
            'title': 'Task with Due Date',
            'due_date': due_date
        })
        assert response.status_code == 201
        assert response.get_json()['task']['due_date'] == due_date

    def test_create_task_with_invalid_due_date(self, client, auth_header):
        response = client.post('/api/tasks', headers=auth_header, json={
            'title': 'Task with Bad Due Date',
            'due_date': 'not-a-date'
        })
        assert response.status_code == 400

    def test_create_task_missing_title(self, client, auth_header):
        response = client.post('/api/tasks', headers=auth_header, json={
            'description': 'No title'
        })
        assert response.status_code == 400

    def test_get_tasks(self, client, auth_header):
        user_id = get_user_by_username(client, 'testuser1')
        with client.application.app_context():
            task1 = Task(title='Task 1', owner_id=user_id, status='pending')
            task2 = Task(title='Task 2', owner_id=user_id, status='completed')
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get('/api/tasks', headers=auth_header)
        assert response.status_code == 200
        assert len(response.get_json()['tasks']) == 2
        assert response.get_json()['pagination']['total'] == 2

    def test_get_tasks_pagination(self, client, auth_header):
        user_id = get_user_by_username(client, 'testuser1')
        with client.application.app_context():
            for i in range(15):
                task = Task(title=f'Task {i}', owner_id=user_id)
                db.session.add(task)
            db.session.commit()

        response = client.get('/api/tasks?page=1&per_page=10', headers=auth_header)
        assert response.status_code == 200
        assert len(response.get_json()['tasks']) == 10
        assert response.get_json()['pagination']['total'] == 15
        assert response.get_json()['pagination']['pages'] == 2

    def test_get_tasks_filter_by_status(self, client, auth_header, user1):
        with client.application.app_context():
            task1 = Task(title='Task 1', owner_id=user1.id, status='pending')
            task2 = Task(title='Task 2', owner_id=user1.id, status='completed')
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get('/api/tasks?status=completed', headers=auth_header)
        assert response.status_code == 200
        assert len(response.get_json()['tasks']) == 1
        assert response.get_json()['tasks'][0]['status'] == 'completed'

    def test_get_tasks_search(self, client, auth_header, user1):
        with client.application.app_context():
            task1 = Task(title='Buy groceries', description='milk', owner_id=user1.id)
            task2 = Task(title='Fix bug', description='critical error', owner_id=user1.id)
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get('/api/tasks?search=groceries', headers=auth_header)
        assert response.status_code == 200
        assert len(response.get_json()['tasks']) == 1
        assert response.get_json()['tasks'][0]['title'] == 'Buy groceries'

    def test_get_single_task(self, client, auth_header, user1):
        with client.application.app_context():
            task = Task(title='Test Task', owner_id=user1.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.get(f'/api/tasks/{task_id}', headers=auth_header)
        assert response.status_code == 200
        assert response.get_json()['title'] == 'Test Task'

    def test_get_task_not_found(self, client, auth_header):
        response = client.get('/api/tasks/999', headers=auth_header)
        assert response.status_code == 404

    def test_get_task_unauthorized(self, client, auth_header, user1, user2):
        with client.application.app_context():
            task = Task(title='User1 Task', owner_id=user2.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.get(f'/api/tasks/{task_id}', headers=auth_header)
        assert response.status_code == 403

    def test_update_task(self, client, auth_header, user1):
        with client.application.app_context():
            task = Task(title='Old Title', owner_id=user1.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.put(f'/api/tasks/{task_id}', headers=auth_header, json={
            'title': 'New Title',
            'status': 'completed'
        })
        assert response.status_code == 200
        assert response.get_json()['task']['title'] == 'New Title'
        assert response.get_json()['task']['status'] == 'completed'

    def test_update_task_with_due_date(self, client, auth_header, user1):
        with client.application.app_context():
            task = Task(title='Task', owner_id=user1.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        due_date = (datetime.utcnow() + timedelta(days=3)).isoformat()
        response = client.put(f'/api/tasks/{task_id}', headers=auth_header, json={
            'due_date': due_date
        })
        assert response.status_code == 200
        assert response.get_json()['task']['due_date'] == due_date

    def test_update_task_clear_due_date(self, client, auth_header, user1):
        with client.application.app_context():
            task = Task(title='Task', owner_id=user1.id, due_date=datetime.utcnow())
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.put(f'/api/tasks/{task_id}', headers=auth_header, json={
            'due_date': None
        })
        assert response.status_code == 200
        assert response.get_json()['task']['due_date'] is None

    def test_update_task_not_found(self, client, auth_header):
        response = client.put('/api/tasks/999', headers=auth_header, json={
            'title': 'New Title'
        })
        assert response.status_code == 404

    def test_update_task_unauthorized(self, client, auth_header, user1, user2):
        with client.application.app_context():
            task = Task(title='User2 Task', owner_id=user2.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.put(f'/api/tasks/{task_id}', headers=auth_header, json={
            'title': 'Hacked'
        })
        assert response.status_code == 403

    def test_delete_task(self, client, auth_header, user1):
        with client.application.app_context():
            task = Task(title='Task to Delete', owner_id=user1.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.delete(f'/api/tasks/{task_id}', headers=auth_header)
        assert response.status_code == 200

        with client.application.app_context():
            deleted_task = Task.query.get(task_id)
            assert deleted_task is None

    def test_delete_task_not_found(self, client, auth_header):
        response = client.delete('/api/tasks/999', headers=auth_header)
        assert response.status_code == 404

    def test_delete_task_unauthorized(self, client, auth_header, user1, user2):
        with client.application.app_context():
            task = Task(title='User2 Task', owner_id=user2.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.delete(f'/api/tasks/{task_id}', headers=auth_header)
        assert response.status_code == 403

    def test_get_assigned_tasks(self, client, auth_header, user1, user2):
        with client.application.app_context():
            task1 = Task(title='Assigned Task 1', owner_id=user2.id, assigned_to=user1.id)
            task2 = Task(title='Assigned Task 2', owner_id=user2.id, assigned_to=user1.id)
            task3 = Task(title='Other Task', owner_id=user1.id, assigned_to=user2.id)
            db.session.add_all([task1, task2, task3])
            db.session.commit()

        response = client.get('/api/tasks/assigned', headers=auth_header)
        assert response.status_code == 200
        assert len(response.get_json()['tasks']) == 2
        assert response.get_json()['tasks'][0]['title'] == 'Assigned Task 1'

    def test_get_assigned_tasks_filter(self, client, auth_header, user1, user2):
        with client.application.app_context():
            task1 = Task(title='Assigned 1', owner_id=user2.id, assigned_to=user1.id, status='pending')
            task2 = Task(title='Assigned 2', owner_id=user2.id, assigned_to=user1.id, status='completed')
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get('/api/tasks/assigned?status=pending', headers=auth_header)
        assert response.status_code == 200
        assert len(response.get_json()['tasks']) == 1
        assert response.get_json()['tasks'][0]['status'] == 'pending'

class TestCategories:
    def test_create_category(self, client, auth_header):
        response = client.post('/api/categories', headers=auth_header, json={
            'name': 'Custom Category',
            'description': 'A custom category'
        })
        assert response.status_code == 201
        assert response.get_json()['category']['name'] == 'Custom Category'

    def test_create_category_missing_name(self, client, auth_header):
        response = client.post('/api/categories', headers=auth_header, json={
            'description': 'No name'
        })
        assert response.status_code == 400

    def test_get_categories(self, client, auth_header):
        response = client.get('/api/categories', headers=auth_header)
        assert response.status_code == 200
        assert len(response.get_json()['categories']) > 0
        assert 'pagination' in response.get_json()

    def test_get_category(self, client, auth_header):
        response = client.get('/api/categories/1', headers=auth_header)
        assert response.status_code == 200
        assert 'name' in response.get_json()

    def test_get_category_not_found(self, client, auth_header):
        response = client.get('/api/categories/999', headers=auth_header)
        assert response.status_code == 404

    def test_update_category(self, client, auth_header):
        response = client.put('/api/categories/1', headers=auth_header, json={
            'name': 'Updated Category'
        })
        assert response.status_code == 200
        assert response.get_json()['category']['name'] == 'Updated Category'

    def test_delete_category(self, client, auth_header):
        with client.application.app_context():
            cat = Category(name='To Delete')
            db.session.add(cat)
            db.session.commit()
            cat_id = cat.id

        response = client.delete(f'/api/categories/{cat_id}', headers=auth_header)
        assert response.status_code == 200

        with client.application.app_context():
            deleted_cat = Category.query.get(cat_id)
            assert deleted_cat is None

class TestPriorities:
    def test_create_priority(self, client, auth_header):
        response = client.post('/api/priorities', headers=auth_header, json={
            'name': 'Custom Priority',
            'level': 5
        })
        assert response.status_code == 201
        assert response.get_json()['priority']['name'] == 'Custom Priority'

    def test_create_priority_missing_fields(self, client, auth_header):
        response = client.post('/api/priorities', headers=auth_header, json={
            'name': 'No Level'
        })
        assert response.status_code == 400

    def test_get_priorities(self, client, auth_header):
        response = client.get('/api/priorities', headers=auth_header)
        assert response.status_code == 200
        assert len(response.get_json()['priorities']) > 0
        assert 'pagination' in response.get_json()

    def test_get_priority(self, client, auth_header):
        response = client.get('/api/priorities/1', headers=auth_header)
        assert response.status_code == 200
        assert 'name' in response.get_json()

    def test_get_priority_not_found(self, client, auth_header):
        response = client.get('/api/priorities/999', headers=auth_header)
        assert response.status_code == 404

    def test_update_priority(self, client, auth_header):
        response = client.put('/api/priorities/1', headers=auth_header, json={
            'name': 'Updated Priority'
        })
        assert response.status_code == 200
        assert response.get_json()['priority']['name'] == 'Updated Priority'

    def test_delete_priority(self, client, auth_header):
        with client.application.app_context():
            pri = Priority(name='To Delete', level=10)
            db.session.add(pri)
            db.session.commit()
            pri_id = pri.id

        response = client.delete(f'/api/priorities/{pri_id}', headers=auth_header)
        assert response.status_code == 200

        with client.application.app_context():
            deleted_pri = Priority.query.get(pri_id)
            assert deleted_pri is None

class TestIntegration:
    def test_complete_workflow(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'integrationuser',
            'email': 'integration@example.com',
            'password': 'password123'
        })
        assert response.status_code == 201

        response = client.post('/api/auth/login', json={
            'username': 'integrationuser',
            'password': 'password123'
        })
        assert response.status_code == 200
        token = response.get_json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}

        response = client.get('/api/categories', headers=headers)
        assert response.status_code == 200
        categories = response.get_json()['categories']
        category_id = categories[0]['id'] if categories else 1

        response = client.get('/api/priorities', headers=headers)
        assert response.status_code == 200
        priorities = response.get_json()['priorities']
        priority_id = priorities[0]['id'] if priorities else 1

        due_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
        response = client.post('/api/tasks', headers=headers, json={
            'title': 'Integration Test Task',
            'description': 'Testing the full workflow',
            'status': 'pending',
            'category_id': category_id,
            'priority_id': priority_id,
            'due_date': due_date
        })
        assert response.status_code == 201
        task_id = response.get_json()['task']['id']

        response = client.get(f'/api/tasks/{task_id}', headers=headers)
        assert response.status_code == 200
        assert response.get_json()['title'] == 'Integration Test Task'

        response = client.put(f'/api/tasks/{task_id}', headers=headers, json={
            'status': 'completed',
            'description': 'Updated description'
        })
        assert response.status_code == 200
        assert response.get_json()['task']['status'] == 'completed'

        response = client.get('/api/tasks?status=completed', headers=headers)
        assert response.status_code == 200
        assert len(response.get_json()['tasks']) == 1

    def test_task_with_assignment(self, client):
        user1_response = client.post('/api/auth/register', json={
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'pass1'
        })
        user1_id = user1_response.get_json()['user']['id']

        user2_response = client.post('/api/auth/register', json={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'pass2'
        })
        user2_id = user2_response.get_json()['user']['id']

        login1 = client.post('/api/auth/login', json={
            'username': 'user1',
            'password': 'pass1'
        })
        headers1 = {'Authorization': f"Bearer {login1.get_json()['access_token']}"}

        login2 = client.post('/api/auth/login', json={
            'username': 'user2',
            'password': 'pass2'
        })
        headers2 = {'Authorization': f"Bearer {login2.get_json()['access_token']}"}

        task_response = client.post('/api/tasks', headers=headers1, json={
            'title': 'Assign to User 2',
            'assigned_to': user2_id
        })
        assert task_response.status_code == 201

        assigned_response = client.get('/api/tasks/assigned', headers=headers2)
        assert assigned_response.status_code == 200
        assert len(assigned_response.get_json()['tasks']) == 1
        assert assigned_response.get_json()['tasks'][0]['title'] == 'Assign to User 2'

class TestHealth:
    def test_health_check(self, client):
        response = client.get('/api/health')
        assert response.status_code == 200
        assert response.get_json()['status'] == 'ok'
