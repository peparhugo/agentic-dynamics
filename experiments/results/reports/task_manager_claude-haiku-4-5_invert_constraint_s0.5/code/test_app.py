import pytest
import json
from datetime import datetime, timedelta
from app import app, db
from models import User, Task, Category, TaskStatus, TaskPriority
from auth import hash_password, generate_token


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['JWT_SECRET_KEY'] = 'test-secret-key'

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def test_user(client):
    with app.app_context():
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash=hash_password('password123')
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id


@pytest.fixture
def test_user2(client):
    with app.app_context():
        user = User(
            username='testuser2',
            email='test2@example.com',
            password_hash=hash_password('password123')
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id


@pytest.fixture
def test_category(client):
    with app.app_context():
        category = Category(
            name='Work',
            description='Work-related tasks'
        )
        db.session.add(category)
        db.session.commit()
        category_id = category.id
    return category_id


@pytest.fixture
def auth_token(test_user):
    with app.app_context():
        return generate_token(test_user)


class TestHealthCheck:
    def test_health_check(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json['status'] == 'ok'


class TestUserRegistration:
    def test_register_success(self, client):
        response = client.post('/auth/register', json={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'password123'
        })
        assert response.status_code == 201
        assert response.json['user']['username'] == 'newuser'
        assert response.json['user']['email'] == 'new@example.com'
        assert 'token' in response.json

    def test_register_missing_fields(self, client):
        response = client.post('/auth/register', json={
            'username': 'newuser'
        })
        assert response.status_code == 400
        assert 'Missing required fields' in response.json['error']

    def test_register_duplicate_username(self, client, test_user):
        response = client.post('/auth/register', json={
            'username': 'testuser',
            'email': 'different@example.com',
            'password': 'password123'
        })
        assert response.status_code == 409
        assert 'Username already exists' in response.json['error']

    def test_register_duplicate_email(self, client, test_user):
        response = client.post('/auth/register', json={
            'username': 'differentuser',
            'email': 'test@example.com',
            'password': 'password123'
        })
        assert response.status_code == 409
        assert 'Email already exists' in response.json['error']


class TestUserLogin:
    def test_login_success(self, client, test_user):
        response = client.post('/auth/login', json={
            'username': 'testuser',
            'password': 'password123'
        })
        assert response.status_code == 200
        assert response.json['user']['username'] == 'testuser'
        assert 'token' in response.json

    def test_login_invalid_username(self, client):
        response = client.post('/auth/login', json={
            'username': 'nonexistent',
            'password': 'password123'
        })
        assert response.status_code == 401
        assert 'Invalid username or password' in response.json['error']

    def test_login_invalid_password(self, client, test_user):
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


class TestCategories:
    def test_create_category(self, client, auth_token):
        response = client.post('/categories',
            json={'name': 'Personal', 'description': 'Personal tasks'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['name'] == 'Personal'

    def test_create_category_missing_token(self, client):
        response = client.post('/categories',
            json={'name': 'Personal'}
        )
        assert response.status_code == 401

    def test_create_category_duplicate(self, client, auth_token, test_category):
        response = client.post('/categories',
            json={'name': 'Work'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 409

    def test_create_category_missing_name(self, client, auth_token):
        response = client.post('/categories',
            json={'description': 'Description only'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400

    def test_get_categories(self, client, auth_token, test_category):
        response = client.get('/categories',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json) > 0


class TestTaskCreation:
    def test_create_task_minimal(self, client, auth_token):
        response = client.post('/tasks',
            json={'title': 'Test Task'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['title'] == 'Test Task'
        assert response.json['status'] == 'pending'
        assert response.json['priority'] == 'medium'

    def test_create_task_full(self, client, auth_token, test_category, test_user2):
        due_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
        response = client.post('/tasks',
            json={
                'title': 'Complete Project',
                'description': 'Finish the project',
                'status': 'in_progress',
                'priority': 'high',
                'category_id': test_category,
                'assigned_to_id': test_user2,
                'due_date': due_date
            },
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 201
        assert response.json['title'] == 'Complete Project'
        assert response.json['priority'] == 'high'
        assert response.json['assigned_to_username'] == 'testuser2'

    def test_create_task_missing_title(self, client, auth_token):
        response = client.post('/tasks',
            json={'description': 'No title'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400

    def test_create_task_invalid_status(self, client, auth_token):
        response = client.post('/tasks',
            json={'title': 'Task', 'status': 'invalid_status'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400

    def test_create_task_invalid_priority(self, client, auth_token):
        response = client.post('/tasks',
            json={'title': 'Task', 'priority': 'invalid_priority'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400

    def test_create_task_invalid_category(self, client, auth_token):
        response = client.post('/tasks',
            json={'title': 'Task', 'category_id': 99999},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404

    def test_create_task_invalid_assigned_user(self, client, auth_token, test_user):
        response = client.post('/tasks',
            json={'title': 'Task', 'assigned_to_id': 99999},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404

    def test_create_task_invalid_due_date_format(self, client, auth_token):
        response = client.post('/tasks',
            json={'title': 'Task', 'due_date': 'invalid-date'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400

    def test_create_task_no_token(self, client):
        response = client.post('/tasks',
            json={'title': 'Task'}
        )
        assert response.status_code == 401


class TestTaskRetrieval:
    def test_get_all_tasks(self, client, auth_token, test_user):
        with app.app_context():
            task = Task(
                title='Task 1',
                owner_id=test_user,
                status='pending'
            )
            db.session.add(task)
            db.session.commit()

        response = client.get('/tasks',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert response.json['total'] == 1

    def test_get_task_by_id(self, client, auth_token, test_user):
        with app.app_context():
            task = Task(
                title='Task 1',
                owner_id=test_user
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.get(f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['title'] == 'Task 1'

    def test_get_task_not_found(self, client, auth_token):
        response = client.get('/tasks/99999',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404

    def test_get_tasks_pagination(self, client, auth_token, test_user):
        with app.app_context():
            for i in range(15):
                task = Task(
                    title=f'Task {i}',
                    owner_id=test_user
                )
                db.session.add(task)
            db.session.commit()

        response = client.get('/tasks?page=1&per_page=10',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 10
        assert response.json['page'] == 1
        assert response.json['pages'] == 2

        response = client.get('/tasks?page=2&per_page=10',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert len(response.json['tasks']) == 5


class TestTaskFiltering:
    def test_filter_by_status(self, client, auth_token, test_user):
        with app.app_context():
            task1 = Task(title='Pending Task', owner_id=test_user, status='pending')
            task2 = Task(title='Completed Task', owner_id=test_user, status='completed')
            db.session.add(task1)
            db.session.add(task2)
            db.session.commit()

        response = client.get('/tasks?status=completed',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert response.json['tasks'][0]['status'] == 'completed'

    def test_filter_by_priority(self, client, auth_token, test_user):
        with app.app_context():
            task1 = Task(title='Low Priority', owner_id=test_user, priority='low')
            task2 = Task(title='High Priority', owner_id=test_user, priority='high')
            db.session.add(task1)
            db.session.add(task2)
            db.session.commit()

        response = client.get('/tasks?priority=high',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert response.json['tasks'][0]['priority'] == 'high'

    def test_filter_by_category(self, client, auth_token, test_user, test_category):
        with app.app_context():
            task = Task(
                title='Categorized Task',
                owner_id=test_user,
                category_id=test_category
            )
            db.session.add(task)
            db.session.commit()

        response = client.get(f'/tasks?category_id={test_category}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1

    def test_search_by_title(self, client, auth_token, test_user):
        with app.app_context():
            task1 = Task(title='Implement Feature', owner_id=test_user)
            task2 = Task(title='Fix Bug', owner_id=test_user)
            db.session.add(task1)
            db.session.add(task2)
            db.session.commit()

        response = client.get('/tasks?search=Feature',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert 'Feature' in response.json['tasks'][0]['title']

    def test_search_by_description(self, client, auth_token, test_user):
        with app.app_context():
            task = Task(
                title='Task',
                description='Important details about implementation',
                owner_id=test_user
            )
            db.session.add(task)
            db.session.commit()

        response = client.get('/tasks?search=implementation',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1

    def test_filter_assigned_to_me(self, client, auth_token, test_user, test_user2):
        with app.app_context():
            task1 = Task(
                title='Assigned to me',
                owner_id=test_user2,
                assigned_to_id=test_user
            )
            task2 = Task(
                title='Assigned to other',
                owner_id=test_user2,
                assigned_to_id=test_user2
            )
            db.session.add(task1)
            db.session.add(task2)
            db.session.commit()

        response = client.get('/tasks?assigned_to_me=true',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1
        assert response.json['tasks'][0]['assigned_to_username'] == 'testuser'

    def test_filter_my_tasks(self, client, auth_token, test_user, test_user2):
        with app.app_context():
            task1 = Task(title='My Task', owner_id=test_user)
            task2 = Task(title='Other Task', owner_id=test_user2)
            db.session.add(task1)
            db.session.add(task2)
            db.session.commit()

        response = client.get('/tasks?my_tasks=true',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['tasks']) == 1

    def test_filter_invalid_status(self, client, auth_token):
        response = client.get('/tasks?status=invalid',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400

    def test_filter_invalid_priority(self, client, auth_token):
        response = client.get('/tasks?priority=invalid',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400


class TestTaskUpdate:
    def test_update_task_success(self, client, auth_token, test_user):
        with app.app_context():
            task = Task(title='Original Title', owner_id=test_user)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.put(f'/tasks/{task_id}',
            json={'title': 'Updated Title'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['title'] == 'Updated Title'

    def test_update_task_all_fields(self, client, auth_token, test_user, test_user2, test_category):
        with app.app_context():
            task = Task(
                title='Original',
                description='Original desc',
                owner_id=test_user,
                status='pending',
                priority='low'
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        due_date = (datetime.utcnow() + timedelta(days=5)).isoformat()
        response = client.put(f'/tasks/{task_id}',
            json={
                'title': 'New Title',
                'description': 'New Description',
                'status': 'completed',
                'priority': 'high',
                'category_id': test_category,
                'assigned_to_id': test_user2,
                'due_date': due_date
            },
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['title'] == 'New Title'
        assert response.json['status'] == 'completed'
        assert response.json['priority'] == 'high'

    def test_update_task_not_found(self, client, auth_token):
        response = client.put('/tasks/99999',
            json={'title': 'Updated'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404

    def test_update_task_not_owner(self, client, auth_token, test_user, test_user2):
        with app.app_context():
            task = Task(title='Task', owner_id=test_user2)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.put(f'/tasks/{task_id}',
            json={'title': 'Hacked'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 403

    def test_update_task_invalid_status(self, client, auth_token, test_user):
        with app.app_context():
            task = Task(title='Task', owner_id=test_user)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.put(f'/tasks/{task_id}',
            json={'status': 'invalid'},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 400

    def test_update_task_clear_due_date(self, client, auth_token, test_user):
        with app.app_context():
            due_date = datetime.utcnow() + timedelta(days=5)
            task = Task(title='Task', owner_id=test_user, due_date=due_date)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.put(f'/tasks/{task_id}',
            json={'due_date': None},
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['due_date'] is None


class TestTaskDelete:
    def test_delete_task_success(self, client, auth_token, test_user):
        with app.app_context():
            task = Task(title='To Delete', owner_id=test_user)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.delete(f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert 'deleted successfully' in response.json['message']

        response = client.get(f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404

    def test_delete_task_not_found(self, client, auth_token):
        response = client.delete('/tasks/99999',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404

    def test_delete_task_not_owner(self, client, auth_token, test_user, test_user2):
        with app.app_context():
            task = Task(title='Task', owner_id=test_user2)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.delete(f'/tasks/{task_id}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 403


class TestUserEndpoints:
    def test_get_current_user(self, client, auth_token, test_user):
        response = client.get('/users/me',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['username'] == 'testuser'
        assert response.json['email'] == 'test@example.com'

    def test_get_user_by_id(self, client, auth_token, test_user):
        response = client.get(f'/users/{test_user}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 200
        assert response.json['username'] == 'testuser'

    def test_get_user_not_found(self, client, auth_token):
        response = client.get('/users/99999',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response.status_code == 404


class TestAuthentication:
    def test_missing_token(self, client):
        response = client.get('/tasks')
        assert response.status_code == 401
        assert 'Token is missing' in response.json['error']

    def test_invalid_token_format(self, client):
        response = client.get('/tasks',
            headers={'Authorization': 'InvalidFormat'}
        )
        assert response.status_code == 401
        assert 'Invalid authorization header format' in response.json['error']

    def test_invalid_token(self, client):
        response = client.get('/tasks',
            headers={'Authorization': 'Bearer invalid.token.here'}
        )
        assert response.status_code == 401
        assert 'invalid or expired' in response.json['error'].lower()
