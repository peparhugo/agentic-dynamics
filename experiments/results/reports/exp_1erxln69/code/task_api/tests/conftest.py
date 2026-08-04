import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.models.user import User
from app.models.task import Task, task_dependencies, task_tags
from app.models.category import Category
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture
def user(db):
    u = User(
        username="testuser",
        email="test@example.com",
        password_hash=generate_password_hash("password123"),
    )
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def auth_header(user, client):
    rv = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "password123",
    })
    token = rv.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user(db):
    u = User(
        username="otheruser",
        email="other@example.com",
        password_hash=generate_password_hash("password456"),
    )
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def second_auth_header(second_user, client):
    rv = client.post("/api/auth/login", json={
        "username": "otheruser",
        "password": "password456",
    })
    token = rv.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def category(user, db):
    c = Category(name="Work", description="Work tasks", color="#ff0000", user_id=user.id)
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture
def task(user, db):
    t = Task(title="Test task", description="A test task", creator_id=user.id)
    db.session.add(t)
    db.session.commit()
    return t


@pytest.fixture
def task_with_deps(user, second_user, category, db):
    parent = Task(
        title="Parent task",
        description="Root of the hierarchy",
        status="in_progress",
        priority="high",
        category_id=category.id,
        creator_id=user.id,
        effort_estimate=8,
    )
    db.session.add(parent)
    db.session.flush()

    child = Task(
        title="Child task",
        description="A sub-task",
        status="pending",
        priority="medium",
        parent_id=parent.id,
        creator_id=user.id,
        assignee_id=second_user.id,
    )
    db.session.add(child)
    db.session.flush()

    parent.dependencies.append(child)
    db.session.execute(task_tags.insert().values(task_id=parent.id, tag="urgent"))
    db.session.execute(task_tags.insert().values(task_id=parent.id, tag="backend"))
    db.session.commit()
    return parent
