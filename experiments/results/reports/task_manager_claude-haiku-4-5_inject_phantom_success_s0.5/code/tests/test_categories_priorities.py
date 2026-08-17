import json
import pytest
from app import db, Category, Priority

class TestCategories:
    def test_categories_exist(self, client, auth_headers):
        with client.application.app_context():
            categories = Category.query.all()
            assert len(categories) == 3
            category_names = [c.name for c in categories]
            assert 'Work' in category_names
            assert 'Personal' in category_names
            assert 'Shopping' in category_names

    def test_category_to_dict(self, client):
        with client.application.app_context():
            category = Category.query.first()
            data = category.to_dict()
            assert 'id' in data
            assert 'name' in data
            assert 'description' in data
            assert 'created_at' in data

class TestPriorities:
    def test_priorities_exist(self, client, auth_headers):
        with client.application.app_context():
            priorities = Priority.query.all()
            assert len(priorities) == 4
            priority_levels = [p.level for p in priorities]
            assert 'low' in priority_levels
            assert 'medium' in priority_levels
            assert 'high' in priority_levels
            assert 'urgent' in priority_levels

    def test_priority_rank_ordering(self, client):
        with client.application.app_context():
            priorities = Priority.query.order_by(Priority.rank).all()
            assert priorities[0].level == 'low'
            assert priorities[1].level == 'medium'
            assert priorities[2].level == 'high'
            assert priorities[3].level == 'urgent'

    def test_priority_to_dict(self, client):
        with client.application.app_context():
            priority = Priority.query.first()
            data = priority.to_dict()
            assert 'id' in data
            assert 'level' in data
            assert 'rank' in data

class TestCategoryTaskRelation:
    def test_category_has_tasks(self, client, auth_headers, test_user):
        with client.application.app_context():
            from app import Task
            category = Category.query.first()
            task = Task(title='Test', category_id=category.id, created_by=test_user.id)
            db.session.add(task)
            db.session.commit()

            category = Category.query.first()
            assert len(category.tasks) == 1
            assert category.tasks[0].title == 'Test'

class TestPriorityTaskRelation:
    def test_priority_has_tasks(self, client, auth_headers, test_user):
        with client.application.app_context():
            from app import Task
            priority = Priority.query.filter_by(level='high').first()
            task = Task(title='Test', priority_id=priority.id, created_by=test_user.id)
            db.session.add(task)
            db.session.commit()

            priority = Priority.query.filter_by(level='high').first()
            assert len(priority.tasks) == 1
            assert priority.tasks[0].title == 'Test'
