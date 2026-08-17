# Task Management System - Polyrhythm API

A complete task management system built with Flask, SQLite, and JWT authentication. Features user registration/login, task CRUD operations, categories, priorities, task assignment, pagination, and advanced search/filtering capabilities.

## Features

- **User Management**
  - User registration and login with JWT authentication
  - Secure password hashing
  - User profile retrieval and listing

- **Task Management**
  - Create, read, update, delete (CRUD) tasks
  - Task status tracking (pending, in_progress, completed, etc.)
  - Task descriptions and due dates
  - Task assignment to users
  - Task creation tracking (who created the task)

- **Task Organization**
  - Categories for grouping related tasks
  - Priority levels (Critical, High, Medium, Low)
  - Flexible category and priority management

- **Search & Filtering**
  - Search tasks by title and description
  - Filter by status, category, priority, and assigned user
  - Combine multiple filters for advanced queries

- **Pagination**
  - Paginated results for all list endpoints
  - Configurable page size

- **Security**
  - JWT-based authentication
  - Protected endpoints requiring valid tokens
  - Password hashing with werkzeug

## Project Structure

```
.
├── app.py                 # Flask application factory
├── config.py             # Configuration (Config and TestConfig)
├── models.py             # SQLAlchemy models (User, Task, Category, Priority)
├── routes.py             # API endpoints and handlers
├── auth.py               # Authentication utilities
├── migrations.py         # Database initialization and seeding
├── test_app.py          # Comprehensive pytest test suite (48 tests)
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Installation

### 1. Clone/Setup the Project

```bash
cd /tmp/exp_zqxlw5wb
```

### 2. Install Dependencies

```bash
python3 -m pip install -r requirements.txt
```

### 3. Initialize Database

```bash
python3 migrations.py
```

This creates the database schema and seeds default categories and priorities.

## Running the Application

### Start Development Server

```bash
python3 app.py
```

The API will be available at `http://localhost:5000`

### Reset Database (Development)

```bash
python3 migrations.py reset
```

## Running Tests

```bash
python3 -m pytest test_app.py -v
```

Run with coverage:

```bash
python3 -m pytest test_app.py --cov=. --cov-report=html
```

## API Endpoints

### Authentication

#### Register User
```
POST /api/auth/register
Content-Type: application/json

{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "securepassword123"
}

Response (201):
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "created_at": "2026-08-15T10:30:00",
    "updated_at": "2026-08-15T10:30:00"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Login User
```
POST /api/auth/login
Content-Type: application/json

{
  "username": "john_doe",
  "password": "securepassword123"
}

Response (200):
{
  "message": "Login successful",
  "user": {...},
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Categories

#### Create Category
```
POST /api/categories
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "Work",
  "description": "Work-related tasks"
}

Response (201): Category object
```

#### List Categories
```
GET /api/categories?page=1&per_page=10
Authorization: Bearer {access_token}

Response (200):
{
  "categories": [...],
  "total": 5,
  "pages": 1,
  "current_page": 1
}
```

#### Get Category
```
GET /api/categories/{category_id}
Authorization: Bearer {access_token}

Response (200): Category object
```

#### Update Category
```
PUT /api/categories/{category_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "Updated Work",
  "description": "Updated description"
}

Response (200): Updated category object
```

#### Delete Category
```
DELETE /api/categories/{category_id}
Authorization: Bearer {access_token}

Response (200): {"message": "Category deleted successfully"}
```

### Priorities

#### Create Priority
```
POST /api/priorities
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "High",
  "level": 1
}

Response (201): Priority object
```

#### List Priorities
```
GET /api/priorities?page=1&per_page=10
Authorization: Bearer {access_token}

Response (200):
{
  "priorities": [...],
  "total": 4,
  "pages": 1,
  "current_page": 1
}
```

### Tasks

#### Create Task
```
POST /api/tasks
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "title": "Complete project proposal",
  "description": "Finish the quarterly project proposal",
  "status": "pending",
  "category_id": 1,
  "priority_id": 2,
  "assigned_to": 2,
  "due_date": "2026-08-25T17:00:00"
}

Response (201): Task object
```

#### List Tasks (with Filters & Pagination)
```
GET /api/tasks?page=1&per_page=10&status=pending&category_id=1&priority_id=2&assigned_to=2&search=project
Authorization: Bearer {access_token}

Query Parameters:
  - page: Page number (default: 1)
  - per_page: Items per page (default: 10)
  - status: Filter by status (e.g., pending, completed)
  - category_id: Filter by category
  - priority_id: Filter by priority
  - assigned_to: Filter by assigned user
  - search: Search in title and description

Response (200):
{
  "tasks": [...],
  "total": 15,
  "pages": 2,
  "current_page": 1
}
```

#### Get Task
```
GET /api/tasks/{task_id}
Authorization: Bearer {access_token}

Response (200): Task object
```

#### Update Task
```
PUT /api/tasks/{task_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "title": "Updated title",
  "status": "in_progress",
  "due_date": "2026-08-30T17:00:00"
}

Response (200): Updated task object
```

#### Delete Task
```
DELETE /api/tasks/{task_id}
Authorization: Bearer {access_token}

Response (200): {"message": "Task deleted successfully"}
```

### Users

#### Get User
```
GET /api/users/{user_id}
Authorization: Bearer {access_token}

Response (200): User object
```

#### List Users
```
GET /api/users?page=1&per_page=10
Authorization: Bearer {access_token}

Response (200):
{
  "users": [...],
  "total": 25,
  "pages": 3,
  "current_page": 1
}
```

## Database Models

### User
- id (Integer, Primary Key)
- username (String, Unique)
- email (String, Unique)
- password_hash (String)
- created_at (DateTime)
- updated_at (DateTime)

### Category
- id (Integer, Primary Key)
- name (String, Unique)
- description (Text)
- created_at (DateTime)

### Priority
- id (Integer, Primary Key)
- name (String, Unique)
- level (Integer) - Numeric priority level (1=highest)
- created_at (DateTime)

### Task
- id (Integer, Primary Key)
- title (String)
- description (Text)
- status (String) - Task status (pending, in_progress, completed, etc.)
- due_date (DateTime, Optional)
- category_id (Foreign Key to Category)
- priority_id (Foreign Key to Priority)
- assigned_to (Foreign Key to User) - User the task is assigned to
- created_by (Foreign Key to User) - User who created the task
- created_at (DateTime)
- updated_at (DateTime)

## Test Suite

The project includes 48 comprehensive tests covering:

### Authentication Tests (7 tests)
- User registration (success, duplicate username, duplicate email, missing fields)
- User login (success, invalid credentials, missing fields)

### Category Tests (10 tests)
- Create, read, update, delete operations
- Duplicate detection
- Pagination
- Missing fields validation

### Priority Tests (4 tests)
- Create and retrieve priorities
- Duplicate detection
- Ordering by level

### Task Tests (21 tests)
- CRUD operations
- Due date handling and validation
- Category and priority assignment
- Filtering by status, category, priority, assigned user
- Search in title and description
- Multiple combined filters
- Pagination

### User Tests (4 tests)
- Get user by ID
- List all users with pagination
- 404 handling

### JWT Protection Tests (4 tests)
- Protected endpoints without token
- Protected endpoints with invalid token
- Endpoint security validation

## Usage Examples

### Complete Workflow Example

```bash
# 1. Register a user
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "email": "alice@example.com",
    "password": "password123"
  }'

# Response includes access_token

# 2. Create a category
curl -X POST http://localhost:5000/api/categories \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Work",
    "description": "Work tasks"
  }'

# 3. Create a priority
curl -X POST http://localhost:5000/api/priorities \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High",
    "level": 1
  }'

# 4. Create a task
curl -X POST http://localhost:5000/api/tasks \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Complete documentation",
    "description": "Write comprehensive API docs",
    "status": "pending",
    "category_id": 1,
    "priority_id": 1,
    "due_date": "2026-08-20T17:00:00"
  }'

# 5. List tasks with filters
curl "http://localhost:5000/api/tasks?status=pending&category_id=1&page=1&per_page=5" \
  -H "Authorization: Bearer {access_token}"

# 6. Search tasks
curl "http://localhost:5000/api/tasks?search=documentation" \
  -H "Authorization: Bearer {access_token}"

# 7. Update a task
curl -X PUT http://localhost:5000/api/tasks/1 \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed"
  }'
```

## Configuration

### Environment Variables

```bash
# Set a custom JWT secret key
export JWT_SECRET_KEY="your-very-secure-secret-key-here"
```

### Config Classes

The system supports two configuration profiles:

**Config** (Production):
- SQLite database at `task_management.db`
- JWT token expiry: 30 days
- Custom JWT secret from environment

**TestConfig** (Testing):
- In-memory SQLite database
- JWT token expiry: 30 days
- Test JWT secret key

## API Response Format

### Success Response

```json
{
  "id": 1,
  "title": "Task Title",
  "description": "Task description",
  "status": "pending",
  "due_date": "2026-08-20T17:00:00",
  "category": {
    "id": 1,
    "name": "Work",
    "description": "Work tasks",
    "created_at": "2026-08-15T10:00:00"
  },
  "priority": {
    "id": 1,
    "name": "High",
    "level": 1,
    "created_at": "2026-08-15T10:00:00"
  },
  "assigned_to": 2,
  "assigned_user": {
    "id": 2,
    "username": "bob",
    "email": "bob@example.com",
    "created_at": "2026-08-15T10:00:00"
  },
  "created_by": 1,
  "creator": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "created_at": "2026-08-15T10:00:00"
  },
  "created_at": "2026-08-15T11:00:00",
  "updated_at": "2026-08-15T11:00:00"
}
```

### Error Response

```json
{
  "error": "Error message describing what went wrong"
}
```

## Security Notes

- Passwords are hashed using werkzeug's security utilities
- JWT tokens include expiration (30 days)
- All protected endpoints require valid JWT token in Authorization header
- SQLAlchemy ORM prevents SQL injection
- Password validation on login

## Performance Considerations

- Database queries use indexed fields (username, email, status, category, priority)
- Pagination prevents loading large result sets into memory
- Lazy loading used for relationships to minimize queries
- Query optimization with filtering before pagination

## Future Enhancements

- User role-based access control (admin, manager, user)
- Task comments and activity history
- Task dependencies and subtasks
- Recurring tasks
- Task notifications and reminders
- File attachments to tasks
- Team collaboration features
- Task templates
- Reporting and analytics dashboard
- Email integration

## License

This project is provided as-is for educational and development purposes.
