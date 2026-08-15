import json
import pytest
from datetime import datetime, timedelta
from app import db, Task, Category, Priority

class TestTaskCreate:
    def test_create_task_success(self, client, auth_headers, test_user_id):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'New Task',
            'description': 'Task description',
            'status': 'todo',
            'category_id': 1,
            'priority_id': 2
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['message'] == 'Task created successfully'
        assert data['task']['title'] == 'New Task'
        assert data['task']['status'] == 'todo'

    def test_create_task_missing_title(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'description': 'Task description'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Title is required' in data['error']

    def test_create_task_with_due_date(self, client, auth_headers):
        due_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task with due date',
            'due_date': due_date
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['task']['due_date'] is not None

    def test_create_task_invalid_due_date(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task with invalid due date',
            'due_date': 'invalid-date'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Invalid due_date format' in data['error']

    def test_create_task_with_assignment(self, client, auth_headers, test_user2_id):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Assigned Task',
            'assigned_to': test_user2_id
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['task']['assigned_to']['id'] == test_user2_id

    def test_create_task_invalid_user_assignment(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'assigned_to': 9999
        })
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'Assigned user not found' in data['error']

    def test_create_task_invalid_category(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'category_id': 9999
        })
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'Category not found' in data['error']

    def test_create_task_invalid_priority(self, client, auth_headers):
        response = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Task',
            'priority_id': 9999
        })
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'Priority not found' in data['error']

class TestTaskRead:
    def test_get_task_success(self, client, auth_headers, test_task_id):
        response = client.get(f'/api/tasks/{test_task_id}', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == test_task_id
        assert data['title'] == 'Test Task'

    def test_get_nonexistent_task(self, client, auth_headers):
        response = client.get('/api/tasks/9999', headers=auth_headers)
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'Task not found' in data['error']

class TestTaskList:
    def test_list_tasks_empty(self, client, auth_headers):
        response = client.get('/api/tasks', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['pagination']['total'] == 0
        assert data['pagination']['page'] == 1

    def test_list_tasks_with_pagination(self, client, auth_headers, test_user_id):
        with client.application.app_context():
            for i in range(15):
                task = Task(
                    title=f'Task {i}',
                    created_by=test_user_id
                )
                db.session.add(task)
            db.session.commit()

        response = client.get('/api/tasks?page=1&per_page=10', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 10
        assert data['pagination']['total'] == 15
        assert data['pagination']['pages'] == 2

    def test_list_tasks_filter_by_status(self, client, auth_headers, test_user_id):
        with client.application.app_context():
            task1 = Task(title='Todo Task', status='todo', created_by=test_user_id)
            task2 = Task(title='Done Task', status='done', created_by=test_user_id)
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get('/api/tasks?status=done', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 1
        assert data['data'][0]['status'] == 'done'

    def test_list_tasks_filter_by_category(self, client, auth_headers, test_user_id):
        with client.application.app_context():
            task1 = Task(title='Work Task', category_id=1, created_by=test_user_id)
            task2 = Task(title='Personal Task', category_id=2, created_by=test_user_id)
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get('/api/tasks?category_id=1', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 1
        assert data['data'][0]['category']['id'] == 1

    def test_list_tasks_filter_by_priority(self, client, auth_headers, test_user_id):
        with client.application.app_context():
            task1 = Task(title='High Priority', priority_id=3, created_by=test_user_id)
            task2 = Task(title='Low Priority', priority_id=1, created_by=test_user_id)
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get('/api/tasks?priority_id=3', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 1
        assert data['data'][0]['priority']['id'] == 3

    def test_list_tasks_filter_by_assigned_user(self, client, auth_headers, test_user_id, test_user2_id):
        with client.application.app_context():
            task1 = Task(title='Task for User1', assigned_to=test_user_id, created_by=test_user_id)
            task2 = Task(title='Task for User2', assigned_to=test_user2_id, created_by=test_user_id)
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get(f'/api/tasks?assigned_to={test_user2_id}', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 1
        assert data['data'][0]['assigned_to']['id'] == test_user2_id

    def test_list_tasks_search(self, client, auth_headers, test_user_id):
        with client.application.app_context():
            task1 = Task(title='Buy groceries', description='For dinner', created_by=test_user_id)
            task2 = Task(title='Finish project', description='Work deadline', created_by=test_user_id)
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get('/api/tasks?search=groceries', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 1
        assert 'groceries' in data['data'][0]['title']

    def test_list_tasks_search_description(self, client, auth_headers, test_user_id):
        with client.application.app_context():
            task1 = Task(title='Project', description='Important deadline', created_by=test_user_id)
            task2 = Task(title='Meeting', description='Team sync', created_by=test_user_id)
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get('/api/tasks?search=deadline', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 1
        assert 'deadline' in data['data'][0]['description']

    def test_list_tasks_multiple_filters(self, client, auth_headers, test_user_id):
        with client.application.app_context():
            task1 = Task(
                title='Work Task',
                status='todo',
                category_id=1,
                priority_id=3,
                created_by=test_user_id
            )
            task2 = Task(
                title='Personal Task',
                status='done',
                category_id=2,
                priority_id=1,
                created_by=test_user_id
            )
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get('/api/tasks?status=todo&category_id=1&priority_id=3', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 1
        assert data['data'][0]['status'] == 'todo'
        assert data['data'][0]['category']['id'] == 1
        assert data['data'][0]['priority']['id'] == 3

    def test_list_tasks_per_page_limit(self, client, auth_headers, test_user_id):
        with client.application.app_context():
            for i in range(200):
                task = Task(title=f'Task {i}', created_by=test_user_id)
                db.session.add(task)
            db.session.commit()

        response = client.get('/api/tasks?per_page=150', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 100

class TestTaskUpdate:
    def test_update_task_title(self, client, auth_headers, test_task_id):
        response = client.put(f'/api/tasks/{test_task_id}', headers=auth_headers, json={
            'title': 'Updated Title'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task']['title'] == 'Updated Title'

    def test_update_task_status(self, client, auth_headers, test_task_id):
        response = client.put(f'/api/tasks/{test_task_id}', headers=auth_headers, json={
            'status': 'in_progress'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task']['status'] == 'in_progress'

    def test_update_task_category(self, client, auth_headers, test_task_id):
        response = client.put(f'/api/tasks/{test_task_id}', headers=auth_headers, json={
            'category_id': 2
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task']['category']['id'] == 2

    def test_update_task_priority(self, client, auth_headers, test_task_id):
        response = client.put(f'/api/tasks/{test_task_id}', headers=auth_headers, json={
            'priority_id': 4
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task']['priority']['id'] == 4

    def test_update_task_due_date(self, client, auth_headers, test_task_id):
        due_date = (datetime.utcnow() + timedelta(days=5)).isoformat()
        response = client.put(f'/api/tasks/{test_task_id}', headers=auth_headers, json={
            'due_date': due_date
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task']['due_date'] is not None

    def test_update_task_clear_due_date(self, client, auth_headers, test_task_id):
        response = client.put(f'/api/tasks/{test_task_id}', headers=auth_headers, json={
            'due_date': None
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task']['due_date'] is None

    def test_update_task_assign_user(self, client, auth_headers, test_task_id, test_user2_id):
        response = client.put(f'/api/tasks/{test_task_id}', headers=auth_headers, json={
            'assigned_to': test_user2_id
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task']['assigned_to']['id'] == test_user2_id

    def test_update_nonexistent_task(self, client, auth_headers):
        response = client.put('/api/tasks/9999', headers=auth_headers, json={
            'title': 'Updated'
        })
        assert response.status_code == 404

    def test_update_task_invalid_category(self, client, auth_headers, test_task_id):
        response = client.put(f'/api/tasks/{test_task_id}', headers=auth_headers, json={
            'category_id': 9999
        })
        assert response.status_code == 404

class TestTaskDelete:
    def test_delete_task_success(self, client, auth_headers, test_task_id):
        response = client.delete(f'/api/tasks/{test_task_id}', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'Task deleted successfully' in data['message']

    def test_delete_nonexistent_task(self, client, auth_headers):
        response = client.delete('/api/tasks/9999', headers=auth_headers)
        assert response.status_code == 404

    def test_delete_task_verify_removal(self, client, auth_headers, test_task_id):
        client.delete(f'/api/tasks/{test_task_id}', headers=auth_headers)
        response = client.get(f'/api/tasks/{test_task_id}', headers=auth_headers)
        assert response.status_code == 404

class TestUserTasks:
    def test_get_user_tasks(self, client, auth_headers, test_user_id, test_user2_id):
        with client.application.app_context():
            task1 = Task(title='Task 1', assigned_to=test_user2_id, created_by=test_user_id)
            task2 = Task(title='Task 2', assigned_to=test_user2_id, created_by=test_user_id)
            task3 = Task(title='Task 3', assigned_to=test_user_id, created_by=test_user_id)
            db.session.add_all([task1, task2, task3])
            db.session.commit()

        response = client.get(f'/api/tasks/user/{test_user2_id}', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['pagination']['total'] == 2

    def test_get_user_tasks_filter_status(self, client, auth_headers, test_user_id, test_user2_id):
        with client.application.app_context():
            task1 = Task(title='Done', status='done', assigned_to=test_user2_id, created_by=test_user_id)
            task2 = Task(title='Todo', status='todo', assigned_to=test_user2_id, created_by=test_user_id)
            db.session.add_all([task1, task2])
            db.session.commit()

        response = client.get(f'/api/tasks/user/{test_user2_id}?status=done', headers=auth_headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']) == 1
        assert data['data'][0]['status'] == 'done'
