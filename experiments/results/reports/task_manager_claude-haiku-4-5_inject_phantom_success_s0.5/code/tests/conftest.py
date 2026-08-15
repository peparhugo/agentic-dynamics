import pytest
import json
from app import create_app, db, User, Category, Priority, Task
from auth import hash_password, create_jwt_token

@pytest.fixture
def app():
    app = create_app('testing')

    with app.app_context():
        db.create_all()

        priorities = [
            Priority(level='low', rank=1),
            Priority(level='medium', rank=2),
            Priority(level='high', rank=3),
            Priority(level='urgent', rank=4),
        ]
        db.session.add_all(priorities)

        categories = [
            Category(name='Work', description='Work-related tasks'),
            Category(name='Personal', description='Personal tasks'),
            Category(name='Shopping', description='Shopping list'),
        ]
        db.session.add_all(categories)

        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def test_user_id(app):
    with app.app_context():
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash=hash_password('password123')
        )
        db.session.add(user)
        db.session.commit()
        return user.id

@pytest.fixture
def test_user(app, test_user_id):
    with app.app_context():
        return User.query.get(test_user_id)

@pytest.fixture
def test_user2_id(app):
    with app.app_context():
        user = User(
            username='testuser2',
            email='test2@example.com',
            password_hash=hash_password('password123')
        )
        db.session.add(user)
        db.session.commit()
        return user.id

@pytest.fixture
def test_user2(app, test_user2_id):
    with app.app_context():
        return User.query.get(test_user2_id)

@pytest.fixture
def auth_token(app, test_user_id):
    with app.app_context():
        user = User.query.get(test_user_id)
        return create_jwt_token(user.id, user.email)

@pytest.fixture
def auth_headers(auth_token):
    return {'Authorization': f'Bearer {auth_token}'}

@pytest.fixture
def test_task_id(app, test_user_id):
    with app.app_context():
        task = Task(
            title='Test Task',
            description='This is a test task',
            status='todo',
            created_by=test_user_id,
            category_id=1,
            priority_id=2
        )
        db.session.add(task)
        db.session.commit()
        return task.id

@pytest.fixture
def test_task(app, test_task_id):
    with app.app_context():
        return Task.query.get(test_task_id)
