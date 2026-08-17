import json
import pytest
from app import db, User

class TestAuthRegister:
    def test_register_success(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'securepass123'
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['message'] == 'User registered successfully'
        assert data['user']['username'] == 'newuser'
        assert data['user']['email'] == 'newuser@example.com'

    def test_register_missing_fields(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'newuser'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_register_short_username(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'ab',
            'email': 'test@example.com',
            'password': 'password123'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Username must be at least 3 characters' in data['error']

    def test_register_short_password(self, client):
        response = client.post('/api/auth/register', json={
            'username': 'newuser',
            'email': 'test@example.com',
            'password': '12345'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Password must be at least 6 characters' in data['error']

    def test_register_duplicate_username(self, client, test_user):
        response = client.post('/api/auth/register', json={
            'username': 'testuser',
            'email': 'newemail@example.com',
            'password': 'password123'
        })
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'Username already exists' in data['error']

    def test_register_duplicate_email(self, client, test_user):
        response = client.post('/api/auth/register', json={
            'username': 'newuser',
            'email': 'test@example.com',
            'password': 'password123'
        })
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'Email already exists' in data['error']

class TestAuthLogin:
    def test_login_success(self, client, test_user):
        response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'password123'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['message'] == 'Login successful'
        assert 'access_token' in data
        assert data['user']['username'] == 'testuser'

    def test_login_missing_credentials(self, client):
        response = client.post('/api/auth/login', json={
            'username': 'testuser'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Missing username or password' in data['error']

    def test_login_invalid_username(self, client):
        response = client.post('/api/auth/login', json={
            'username': 'nonexistent',
            'password': 'password123'
        })
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid username or password' in data['error']

    def test_login_invalid_password(self, client, test_user):
        response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid username or password' in data['error']

class TestAuthToken:
    def test_protected_route_without_token(self, client):
        response = client.get('/api/tasks')
        assert response.status_code == 401

    def test_protected_route_with_valid_token(self, client, test_user, auth_headers):
        response = client.get('/api/tasks', headers=auth_headers)
        assert response.status_code == 200

    def test_protected_route_with_invalid_token(self, client):
        headers = {'Authorization': 'Bearer invalidtoken'}
        response = client.get('/api/tasks', headers=headers)
        assert response.status_code == 401

    def test_protected_route_invalid_token_format(self, client):
        headers = {'Authorization': 'InvalidFormat'}
        response = client.get('/api/tasks', headers=headers)
        assert response.status_code == 401
