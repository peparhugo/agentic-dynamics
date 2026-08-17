import pytest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import Task


@pytest.fixture
def app():
    app = create_app('config.TestConfig')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def app_context(app):
    with app.app_context():
        yield


class TestTaskCreation:
    def test_create_task_minimal(self, client):
        response = client.post(
            '/api/tasks',
            json={'title': 'Test Task'}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['title'] == 'Test Task'
        assert data['status'] == 'pending'
        assert data['priority'] == 'medium'
        assert data['description'] is None

    def test_create_task_full(self, client):
        due_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
        response = client.post(
            '/api/tasks',
            json={
                'title': 'Complete Task',
                'description': 'A detailed description',
                'status': 'in_progress',
                'priority': 'high',
                'due_date': due_date,
            }
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['title'] == 'Complete Task'
        assert data['description'] == 'A detailed description'
        assert data['status'] == 'in_progress'
        assert data['priority'] == 'high'
        assert data['due_date'] is not None

    def test_create_task_missing_title(self, client):
        response = client.post(
            '/api/tasks',
            json={'description': 'No title'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'errors' in data
        assert 'title' in data['errors']

    def test_create_task_empty_title(self, client):
        response = client.post(
            '/api/tasks',
            json={'title': '   '}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'errors' in data

    def test_create_task_invalid_status(self, client):
        response = client.post(
            '/api/tasks',
            json={
                'title': 'Task',
                'status': 'invalid_status'
            }
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'status' in data['errors']

    def test_create_task_invalid_priority(self, client):
        response = client.post(
            '/api/tasks',
            json={
                'title': 'Task',
                'priority': 'critical'
            }
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'priority' in data['errors']

    def test_create_task_invalid_due_date(self, client):
        response = client.post(
            '/api/tasks',
            json={
                'title': 'Task',
                'due_date': 'not-a-date'
            }
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'due_date' in data['errors']

    def test_create_task_non_json(self, client):
        response = client.post(
            '/api/tasks',
            data='not json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data


class TestTaskRetrieval:
    def test_get_task(self, client, app_context):
        task = Task(title='Get Me', description='Test')
        db.session.add(task)
        db.session.commit()

        response = client.get(f'/api/tasks/{task.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == task.id
        assert data['title'] == 'Get Me'

    def test_get_nonexistent_task(self, client):
        response = client.get('/api/tasks/999')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_list_tasks_empty(self, client):
        response = client.get('/api/tasks')
        assert response.status_code == 200
        data = response.get_json()
        assert data['tasks'] == []
        assert data['total'] == 0
        assert data['pages'] == 0

    def test_list_tasks_with_data(self, client, app_context):
        for i in range(5):
            task = Task(title=f'Task {i}')
            db.session.add(task)
        db.session.commit()

        response = client.get('/api/tasks')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['tasks']) == 5
        assert data['total'] == 5

    def test_list_tasks_pagination(self, client, app_context):
        for i in range(15):
            task = Task(title=f'Task {i}')
            db.session.add(task)
        db.session.commit()

        response = client.get('/api/tasks?page=1&per_page=5')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['tasks']) == 5
        assert data['total'] == 15
        assert data['pages'] == 3
        assert data['current_page'] == 1

        response = client.get('/api/tasks?page=2&per_page=5')
        data = response.get_json()
        assert data['current_page'] == 2

    def test_list_tasks_filter_by_status(self, client, app_context):
        Task.query.delete()
        t1 = Task(title='Task 1', status='pending')
        t2 = Task(title='Task 2', status='completed')
        t3 = Task(title='Task 3', status='pending')
        db.session.add_all([t1, t2, t3])
        db.session.commit()

        response = client.get('/api/tasks?status=pending')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['tasks']) == 2
        assert all(t['status'] == 'pending' for t in data['tasks'])

    def test_list_tasks_filter_by_priority(self, client, app_context):
        Task.query.delete()
        t1 = Task(title='Task 1', priority='high')
        t2 = Task(title='Task 2', priority='low')
        t3 = Task(title='Task 3', priority='high')
        db.session.add_all([t1, t2, t3])
        db.session.commit()

        response = client.get('/api/tasks?priority=high')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['tasks']) == 2
        assert all(t['priority'] == 'high' for t in data['tasks'])


class TestTaskUpdate:
    def test_update_task_title(self, client, app_context):
        task = Task(title='Old Title')
        db.session.add(task)
        db.session.commit()

        response = client.put(
            f'/api/tasks/{task.id}',
            json={'title': 'New Title'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'New Title'

    def test_update_task_all_fields(self, client, app_context):
        task = Task(title='Original')
        db.session.add(task)
        db.session.commit()

        due_date = (datetime.utcnow() + timedelta(days=5)).isoformat()
        response = client.put(
            f'/api/tasks/{task.id}',
            json={
                'title': 'Updated',
                'description': 'New description',
                'status': 'in_progress',
                'priority': 'high',
                'due_date': due_date,
            }
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'Updated'
        assert data['description'] == 'New description'
        assert data['status'] == 'in_progress'
        assert data['priority'] == 'high'

    def test_update_task_nonexistent(self, client):
        response = client.put(
            '/api/tasks/999',
            json={'title': 'New Title'}
        )
        assert response.status_code == 404

    def test_update_task_invalid_status(self, client, app_context):
        task = Task(title='Task')
        db.session.add(task)
        db.session.commit()

        response = client.put(
            f'/api/tasks/{task.id}',
            json={'status': 'unknown'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'status' in data['errors']

    def test_update_task_status_to_completed(self, client, app_context):
        task = Task(title='Task', status='pending')
        db.session.add(task)
        db.session.commit()
        assert task.completed_at is None

        response = client.put(
            f'/api/tasks/{task.id}',
            json={'status': 'completed'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'completed'
        assert data['completed_at'] is not None

    def test_update_task_clear_due_date(self, client, app_context):
        due = datetime.utcnow() + timedelta(days=1)
        task = Task(title='Task', due_date=due)
        db.session.add(task)
        db.session.commit()

        response = client.put(
            f'/api/tasks/{task.id}',
            json={'due_date': None}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['due_date'] is None

    def test_update_task_non_json(self, client, app_context):
        task = Task(title='Task')
        db.session.add(task)
        db.session.commit()

        response = client.put(
            f'/api/tasks/{task.id}',
            data='not json'
        )
        assert response.status_code == 400


class TestTaskDeletion:
    def test_delete_task(self, client, app_context):
        task = Task(title='Delete Me')
        db.session.add(task)
        db.session.commit()
        task_id = task.id

        response = client.delete(f'/api/tasks/{task_id}')
        assert response.status_code == 204

        assert db.session.get(Task, task_id) is None

    def test_delete_nonexistent_task(self, client):
        response = client.delete('/api/tasks/999')
        assert response.status_code == 404


class TestTaskStatusEndpoint:
    def test_patch_task_status(self, client, app_context):
        task = Task(title='Task', status='pending')
        db.session.add(task)
        db.session.commit()

        response = client.patch(
            f'/api/tasks/{task.id}/status',
            json={'status': 'in_progress'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'in_progress'

    def test_patch_task_status_to_completed(self, client, app_context):
        task = Task(title='Task', status='in_progress', completed_at=None)
        db.session.add(task)
        db.session.commit()

        response = client.patch(
            f'/api/tasks/{task.id}/status',
            json={'status': 'completed'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'completed'
        assert data['completed_at'] is not None

    def test_patch_task_status_missing_field(self, client, app_context):
        task = Task(title='Task')
        db.session.add(task)
        db.session.commit()

        response = client.patch(
            f'/api/tasks/{task.id}/status',
            json={}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_patch_task_status_invalid(self, client, app_context):
        task = Task(title='Task')
        db.session.add(task)
        db.session.commit()

        response = client.patch(
            f'/api/tasks/{task.id}/status',
            json={'status': 'invalid'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_patch_task_status_nonexistent(self, client):
        response = client.patch(
            '/api/tasks/999/status',
            json={'status': 'completed'}
        )
        assert response.status_code == 404


class TestTaskSearch:
    def test_search_by_title(self, client, app_context):
        Task.query.delete()
        t1 = Task(title='Python Tutorial')
        t2 = Task(title='JavaScript Basics')
        t3 = Task(title='Python Advanced')
        db.session.add_all([t1, t2, t3])
        db.session.commit()

        response = client.get('/api/tasks/search?q=Python')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['tasks']) == 2
        assert all('Python' in t['title'] for t in data['tasks'])

    def test_search_by_description(self, client, app_context):
        Task.query.delete()
        t1 = Task(title='Task 1', description='Contains database info')
        t2 = Task(title='Task 2', description='No match here')
        db.session.add_all([t1, t2])
        db.session.commit()

        response = client.get('/api/tasks/search?q=database')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['tasks']) == 1
        assert 'database' in data['tasks'][0]['description']

    def test_search_no_results(self, client, app_context):
        Task.query.delete()
        t1 = Task(title='Task 1')
        db.session.add(t1)
        db.session.commit()

        response = client.get('/api/tasks/search?q=nonexistent')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['tasks']) == 0
        assert data['total'] == 0

    def test_search_missing_query(self, client):
        response = client.get('/api/tasks/search')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_search_case_insensitive(self, client, app_context):
        Task.query.delete()
        t1 = Task(title='PYTHON')
        t2 = Task(title='Other')
        db.session.add_all([t1, t2])
        db.session.commit()

        response = client.get('/api/tasks/search?q=python')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['tasks']) == 1


class TestTaskStats:
    def test_get_stats_empty(self, client):
        Task.query.delete()
        response = client.get('/api/tasks/stats')
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] == 0
        assert data['by_status']['pending'] == 0

    def test_get_stats_with_tasks(self, client, app_context):
        Task.query.delete()
        tasks = [
            Task(title='P1', status='pending', priority='high'),
            Task(title='P2', status='in_progress', priority='medium'),
            Task(title='P3', status='completed', priority='low'),
            Task(title='P4', status='pending', priority='high'),
            Task(title='P5', status='cancelled', priority='medium'),
        ]
        db.session.add_all(tasks)
        db.session.commit()

        response = client.get('/api/tasks/stats')
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] == 5
        assert data['by_status']['pending'] == 2
        assert data['by_status']['in_progress'] == 1
        assert data['by_status']['completed'] == 1
        assert data['by_status']['cancelled'] == 1
        assert data['by_priority']['high'] == 2
        assert data['by_priority']['medium'] == 2
        assert data['by_priority']['low'] == 1


class TestDataValidation:
    def test_title_whitespace_trimming(self, client):
        response = client.post(
            '/api/tasks',
            json={'title': '  Trimmed Title  '}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['title'] == 'Trimmed Title'

    def test_description_whitespace_handling(self, client):
        response = client.post(
            '/api/tasks',
            json={
                'title': 'Task',
                'description': '  Some description  '
            }
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['description'] == 'Some description'

    def test_empty_description_becomes_none(self, client):
        response = client.post(
            '/api/tasks',
            json={
                'title': 'Task',
                'description': '   '
            }
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['description'] is None

    def test_valid_priority_values(self, client):
        for priority in ['low', 'medium', 'high']:
            response = client.post(
                '/api/tasks',
                json={
                    'title': f'Task {priority}',
                    'priority': priority
                }
            )
            assert response.status_code == 201
            data = response.get_json()
            assert data['priority'] == priority

    def test_valid_status_values(self, client):
        for status in ['pending', 'in_progress', 'completed', 'cancelled']:
            response = client.post(
                '/api/tasks',
                json={
                    'title': f'Task {status}',
                    'status': status
                }
            )
            assert response.status_code == 201
            data = response.get_json()
            assert data['status'] == status


class TestErrorHandling:
    def test_invalid_route(self, client):
        response = client.get('/api/invalid')
        assert response.status_code == 404

    def test_malformed_json(self, client):
        response = client.post(
            '/api/tasks',
            data='{invalid json}',
            content_type='application/json'
        )
        assert response.status_code in [400, 500]

    def test_negative_task_id(self, client):
        response = client.get('/api/tasks/-1')
        assert response.status_code == 404

    def test_string_task_id(self, client):
        response = client.get('/api/tasks/abc')
        assert response.status_code == 404


class TestIntegration:
    def test_full_workflow(self, client, app_context):
        task_data = {
            'title': 'Integration Test Task',
            'description': 'Testing full workflow',
            'priority': 'high'
        }
        response = client.post('/api/tasks', json=task_data)
        assert response.status_code == 201
        task = response.get_json()
        task_id = task['id']

        response = client.get(f'/api/tasks/{task_id}')
        assert response.status_code == 200
        assert response.get_json()['title'] == task_data['title']

        response = client.put(
            f'/api/tasks/{task_id}',
            json={'status': 'in_progress'}
        )
        assert response.status_code == 200
        assert response.get_json()['status'] == 'in_progress'

        response = client.patch(
            f'/api/tasks/{task_id}/status',
            json={'status': 'completed'}
        )
        assert response.status_code == 200
        assert response.get_json()['status'] == 'completed'

        response = client.delete(f'/api/tasks/{task_id}')
        assert response.status_code == 204

        response = client.get(f'/api/tasks/{task_id}')
        assert response.status_code == 404

    def test_concurrent_updates_safety(self, client, app_context):
        task = Task(title='Original')
        db.session.add(task)
        db.session.commit()
        task_id = task.id

        response1 = client.put(
            f'/api/tasks/{task_id}',
            json={'title': 'Update 1'}
        )
        assert response1.status_code == 200

        response2 = client.put(
            f'/api/tasks/{task_id}',
            json={'status': 'completed'}
        )
        assert response2.status_code == 200

        response = client.get(f'/api/tasks/{task_id}')
        data = response.get_json()
        assert data['title'] == 'Update 1'
        assert data['status'] == 'completed'
