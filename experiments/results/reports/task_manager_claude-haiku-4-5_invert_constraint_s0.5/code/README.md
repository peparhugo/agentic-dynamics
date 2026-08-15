# Task Management API

A comprehensive task management API built with Flask and SQLite. Includes user authentication with JWT, complete CRUD operations for tasks, advanced filtering and search capabilities, and a full test suite with 51 passing tests.

## Features

### Authentication
- User registration with email and password
- JWT-based authentication for all protected endpoints
- Secure password hashing using SHA-256
- Token expiration and validation

### Task Management
- Create, read, update, and delete tasks
- Task status tracking (pending, in_progress, completed, cancelled)
- Task priority levels (low, medium, high, urgent)
- Task categories for organization
- Due date support with ISO format
- Task assignment to other users

### Filtering & Search
- Filter tasks by status, priority, or category
- Full-text search in task titles and descriptions
- View only my tasks or tasks assigned to me
- Pagination support for large result sets

### Database
- SQLite database with SQLAlchemy ORM
- Indexes on frequently queried columns for performance
- Relationship management between users, tasks, and categories

## Installation

1. Install dependencies:
```bash
python3 -m pip install -r requirements.txt
```

2. Run the application:
```bash
python3 -c "from app import app; app.run(debug=True)"
```

The API will be available at `http://localhost:5000`

## API Endpoints

### Authentication

#### Register User
```
POST /auth/register
Content-Type: application/json

{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password"
}

Response: 201 Created
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "created_at": "2025-01-01T12:00:00",
    "updated_at": "2025-01-01T12:00:00"
  },
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

#### Login
```
POST /auth/login
Content-Type: application/json

{
  "username": "john_doe",
  "password": "secure_password"
}

Response: 200 OK
{
  "message": "Login successful",
  "user": { ... },
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### Categories

#### Create Category
```
POST /categories
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Work",
  "description": "Work-related tasks"
}

Response: 201 Created
{
  "id": 1,
  "name": "Work",
  "description": "Work-related tasks",
  "created_at": "2025-01-01T12:00:00"
}
```

#### Get All Categories
```
GET /categories
Authorization: Bearer {token}

Response: 200 OK
[
  {
    "id": 1,
    "name": "Work",
    "description": "Work-related tasks",
    "created_at": "2025-01-01T12:00:00"
  }
]
```

### Tasks

#### Create Task
```
POST /tasks
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "Implement login feature",
  "description": "Add JWT-based authentication",
  "status": "in_progress",
  "priority": "high",
  "category_id": 1,
  "assigned_to_id": 2,
  "due_date": "2025-02-01T18:00:00"
}

Response: 201 Created
{
  "id": 1,
  "title": "Implement login feature",
  "description": "Add JWT-based authentication",
  "status": "in_progress",
  "priority": "high",
  "owner_id": 1,
  "owner": { ... },
  "category_id": 1,
  "category_name": "Work",
  "assigned_to_id": 2,
  "assigned_to_username": "jane_doe",
  "due_date": "2025-02-01T18:00:00",
  "created_at": "2025-01-01T12:00:00",
  "updated_at": "2025-01-01T12:00:00"
}
```

#### Get All Tasks (with filtering)
```
GET /tasks?page=1&per_page=10&status=in_progress&priority=high&search=login
Authorization: Bearer {token}

Response: 200 OK
{
  "tasks": [ ... ],
  "total": 5,
  "page": 1,
  "per_page": 10,
  "pages": 1
}
```

Query parameters:
- `page` (default: 1): Page number for pagination
- `per_page` (default: 10): Items per page
- `status` (optional): Filter by status (pending, in_progress, completed, cancelled)
- `priority` (optional): Filter by priority (low, medium, high, urgent)
- `category_id` (optional): Filter by category ID
- `search` (optional): Search in title and description
- `my_tasks` (default: false): Show only tasks I own
- `assigned_to_me` (default: false): Show only tasks assigned to me

#### Get Single Task
```
GET /tasks/{task_id}
Authorization: Bearer {token}

Response: 200 OK
{ ... }
```

#### Update Task
```
PUT /tasks/{task_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "Updated title",
  "status": "completed",
  "priority": "medium"
}

Response: 200 OK
{ ... }
```

#### Delete Task
```
DELETE /tasks/{task_id}
Authorization: Bearer {token}

Response: 200 OK
{
  "message": "Task deleted successfully"
}
```

### Users

#### Get Current User
```
GET /users/me
Authorization: Bearer {token}

Response: 200 OK
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "created_at": "2025-01-01T12:00:00",
  "updated_at": "2025-01-01T12:00:00"
}
```

#### Get User by ID
```
GET /users/{user_id}
Authorization: Bearer {token}

Response: 200 OK
{ ... }
```

## Task Status Options
- `pending` - Task is pending
- `in_progress` - Task is being worked on
- `completed` - Task is complete
- `cancelled` - Task has been cancelled

## Task Priority Options
- `low` - Low priority
- `medium` - Medium priority
- `high` - High priority
- `urgent` - Urgent/critical priority

## Error Responses

All error responses follow this format:
```json
{
  "error": "Error message describing what went wrong"
}
```

Common status codes:
- `400` - Bad request (validation error)
- `401` - Unauthorized (missing or invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not found
- `409` - Conflict (duplicate resource)
- `500` - Internal server error

## Running Tests

Run the comprehensive test suite:
```bash
python3 -m pytest test_app.py -v
```

Run with coverage:
```bash
python3 -m pytest test_app.py --cov=app --cov=models --cov=auth --cov-report=html
```

Test coverage includes:
- **Health checks** (1 test)
- **User registration** (4 tests)
- **User login** (4 tests)
- **Category management** (5 tests)
- **Task creation** (9 tests)
- **Task retrieval** (4 tests)
- **Task filtering** (9 tests)
- **Task updates** (6 tests)
- **Task deletion** (3 tests)
- **User endpoints** (3 tests)
- **Authentication** (3 tests)

**Total: 51 passing tests**

## Database Schema

### Users Table
- `id` (Primary Key): User ID
- `username` (Unique): Username
- `email` (Unique): Email address
- `password_hash`: Hashed password
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

### Categories Table
- `id` (Primary Key): Category ID
- `name` (Unique): Category name
- `description`: Category description
- `created_at`: Creation timestamp

### Tasks Table
- `id` (Primary Key): Task ID
- `title`: Task title
- `description`: Task description
- `status`: Task status (indexed)
- `priority`: Task priority (indexed)
- `owner_id` (Foreign Key): User who created the task
- `category_id` (Foreign Key, Optional): Task category
- `assigned_to_id` (Foreign Key, Optional): User task is assigned to
- `due_date`: Task due date
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

## Security Considerations

1. **Password Hashing**: Passwords are hashed using SHA-256
2. **JWT Tokens**: Tokens expire after 24 hours by default
3. **Authorization**: Tasks can only be modified/deleted by their owner
4. **Validation**: All inputs are validated before processing
5. **Indexes**: Database indexes on frequently queried columns for performance

For production:
- Use a strong JWT secret key (set via `JWT_SECRET_KEY` environment variable)
- Use HTTPS for all communications
- Implement rate limiting
- Add CORS configuration as needed
- Use bcrypt or Argon2 for password hashing

## Example Usage

### Register and Login
```bash
curl -X POST http://localhost:5000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "secret123"}'

# Response includes token
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

### Create a Task
```bash
curl -X POST http://localhost:5000/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Build API",
    "description": "Create task management API",
    "priority": "high"
  }'
```

### Search Tasks
```bash
curl -X GET "http://localhost:5000/tasks?search=API&priority=high" \
  -H "Authorization: Bearer $TOKEN"
```

### Update Task Status
```bash
curl -X PUT http://localhost:5000/tasks/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

## License

MIT
