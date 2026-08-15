# Task Management API - Complete Documentation

## Overview

A production-ready REST API for task management built with Flask, SQLAlchemy, and SQLite. The API provides full CRUD operations, search functionality, filtering, pagination, and statistics.

## Project Structure

```
├── app/
│   ├── __init__.py       # Flask app factory with database initialization
│   ├── models.py         # SQLAlchemy Task model with validation and serialization
│   └── routes.py         # REST API endpoints with comprehensive error handling
├── tests/
│   ├── __init__.py       # Test package marker
│   └── test_api.py       # 47 comprehensive pytest tests covering all functionality
├── config.py             # Configuration for different environments
├── run.py                # Application entry point
├── requirements.txt      # Python dependencies
└── pytest.ini            # Pytest configuration
```

## Technology Stack

- **Framework**: Flask 3.0.0 - Lightweight web framework
- **Database**: SQLite with SQLAlchemy ORM
- **Migrations**: Flask-Migrate for database versioning
- **Testing**: pytest 8.4.0 with comprehensive test coverage
- **Validation**: Built-in input validation and error handling

## Database Schema

### Task Model

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    priority VARCHAR(50) DEFAULT 'medium',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    due_date DATETIME,
    completed_at DATETIME
);
```

**Fields:**
- `id` - Unique identifier
- `title` - Required task title (255 chars max)
- `description` - Optional detailed description
- `status` - One of: `pending`, `in_progress`, `completed`, `cancelled`
- `priority` - One of: `low`, `medium`, `high`
- `created_at` - Auto-set on creation
- `updated_at` - Auto-updated on changes
- `due_date` - Optional deadline
- `completed_at` - Auto-set when marked completed

## API Endpoints

### Core CRUD Operations

#### 1. List Tasks
```
GET /api/tasks
```

**Query Parameters:**
- `page` (int, default=1) - Page number for pagination
- `per_page` (int, default=10) - Items per page
- `status` (string) - Filter by status
- `priority` (string) - Filter by priority

**Response (200 OK):**
```json
{
  "tasks": [...],
  "total": 45,
  "pages": 5,
  "current_page": 1
}
```

**Example:**
```bash
curl "http://localhost:5000/api/tasks?page=1&per_page=10&status=pending"
```

---

#### 2. Create Task
```
POST /api/tasks
```

**Request Body:**
```json
{
  "title": "Complete project",
  "description": "Finish the API implementation",
  "priority": "high",
  "status": "pending",
  "due_date": "2024-12-31T23:59:59"
}
```

**Fields:**
- `title` (required) - Task title, non-empty string
- `description` (optional) - Task details
- `priority` (optional, default="medium") - `low|medium|high`
- `status` (optional, default="pending") - Initial status
- `due_date` (optional) - ISO format datetime

**Response (201 Created):**
```json
{
  "id": 1,
  "title": "Complete project",
  "description": "Finish the API implementation",
  "status": "pending",
  "priority": "high",
  "due_date": "2024-12-31T23:59:59",
  "completed_at": null,
  "created_at": "2024-12-01T00:00:00",
  "updated_at": "2024-12-01T00:00:00"
}
```

**Example:**
```bash
curl -X POST http://localhost:5000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Complete project",
    "priority": "high"
  }'
```

---

#### 3. Get Task
```
GET /api/tasks/<id>
```

**Response (200 OK):**
```json
{
  "id": 1,
  "title": "Complete project",
  "description": "...",
  "status": "pending",
  "priority": "high",
  "due_date": "2024-12-31T23:59:59",
  "completed_at": null,
  "created_at": "2024-12-01T00:00:00",
  "updated_at": "2024-12-01T00:00:00"
}
```

**Error Response (404 Not Found):**
```json
{
  "error": "Task not found"
}
```

**Example:**
```bash
curl http://localhost:5000/api/tasks/1
```

---

#### 4. Update Task
```
PUT /api/tasks/<id>
```

**Request Body (any combination of fields):**
```json
{
  "title": "Updated title",
  "description": "Updated description",
  "status": "in_progress",
  "priority": "high",
  "due_date": "2024-12-31T23:59:59"
}
```

**Response (200 OK):** Updated task object

**Validation:**
- `status` must be one of: `pending|in_progress|completed|cancelled`
- `priority` must be one of: `low|medium|high`
- `due_date` must be valid ISO format
- Setting status to `completed` auto-sets `completed_at`

**Example:**
```bash
curl -X PUT http://localhost:5000/api/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'
```

---

#### 5. Delete Task
```
DELETE /api/tasks/<id>
```

**Response (204 No Content):** Empty response

**Example:**
```bash
curl -X DELETE http://localhost:5000/api/tasks/1
```

---

#### 6. Quick Status Update
```
PATCH /api/tasks/<id>/status
```

**Request Body:**
```json
{
  "status": "completed"
}
```

**Response (200 OK):** Updated task object

**Example:**
```bash
curl -X PATCH http://localhost:5000/api/tasks/1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

---

### Search & Analytics

#### 7. Search Tasks
```
GET /api/tasks/search?q=<query>
```

**Query Parameters:**
- `q` (required) - Search query

**Search Scope:**
- Searches task titles (case-insensitive)
- Searches task descriptions (case-insensitive)

**Response (200 OK):**
```json
{
  "tasks": [...],
  "total": 5
}
```

**Example:**
```bash
curl "http://localhost:5000/api/tasks/search?q=database"
```

---

#### 8. Task Statistics
```
GET /api/tasks/stats
```

**Response (200 OK):**
```json
{
  "total": 50,
  "by_status": {
    "pending": 20,
    "in_progress": 15,
    "completed": 10,
    "cancelled": 5
  },
  "by_priority": {
    "low": 10,
    "medium": 25,
    "high": 15
  }
}
```

**Example:**
```bash
curl http://localhost:5000/api/tasks/stats
```

---

## Input Validation

### Title Validation
- Required field
- Must be non-empty string
- Whitespace is trimmed automatically
- Maximum 255 characters

### Description Validation
- Optional field
- Empty/whitespace-only descriptions become `null`
- No maximum length

### Status Validation
- Must be one of: `pending`, `in_progress`, `completed`, `cancelled`
- Default value: `pending`
- Setting to `completed` auto-sets `completed_at` timestamp

### Priority Validation
- Must be one of: `low`, `medium`, `high`
- Default value: `medium`

### Due Date Validation
- Optional field
- Must be valid ISO 8601 format (e.g., `2024-12-31T23:59:59`)
- Supports timezone notation

### Error Responses (400 Bad Request)

**Validation Error:**
```json
{
  "errors": {
    "title": "Title is required",
    "status": "Status must be one of: pending, in_progress, completed, cancelled"
  }
}
```

**Format Error:**
```json
{
  "error": "Request must be JSON"
}
```

---

## HTTP Status Codes

| Code | Meaning | Scenarios |
|------|---------|-----------|
| 200 | OK | Successful GET, PUT, PATCH |
| 201 | Created | Successful POST |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Validation errors, malformed JSON |
| 404 | Not Found | Task ID doesn't exist, invalid route |
| 500 | Server Error | Unhandled exceptions |

---

## Error Handling

All endpoints include comprehensive error handling:

1. **Input Validation** - Validates all user inputs before database operations
2. **Not Found Handling** - Returns 404 for non-existent resources
3. **JSON Validation** - Requires Content-Type: application/json
4. **Database Rollback** - Automatic rollback on database errors
5. **Error Messages** - Clear, descriptive error messages

**Example Error Response:**
```json
{
  "error": "Task not found"
}
```

---

## Testing

### Test Coverage
- **47 comprehensive tests** covering all functionality
- **100% endpoint coverage** - All API routes tested
- **Validation tests** - Input validation for all fields
- **Error handling tests** - Edge cases and error conditions
- **Integration tests** - Full workflow from creation to deletion

### Test Categories

1. **Task Creation** (8 tests)
   - Minimal and full task creation
   - Field validation (title, status, priority, due_date)
   - Error cases (missing required fields, invalid values)

2. **Task Retrieval** (7 tests)
   - Get single task
   - List tasks with pagination
   - Filtering by status and priority
   - Empty results handling

3. **Task Updates** (7 tests)
   - Update individual fields
   - Update all fields
   - Status transitions
   - Completion timestamp handling

4. **Task Deletion** (2 tests)
   - Delete existing task
   - Handle non-existent task

5. **Status Endpoint** (5 tests)
   - Quick status updates
   - Completion tracking
   - Validation and error cases

6. **Search** (5 tests)
   - Title search
   - Description search
   - Case-insensitive matching
   - Error handling

7. **Statistics** (2 tests)
   - Empty database stats
   - Stats with various tasks

8. **Data Validation** (5 tests)
   - Whitespace trimming
   - Type validation
   - Enum value validation

9. **Error Handling** (4 tests)
   - Invalid routes
   - Malformed JSON
   - Invalid task IDs

10. **Integration** (2 tests)
    - Full workflow (create → read → update → delete)
    - Concurrent update safety

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test class
pytest tests/test_api.py::TestTaskCreation -v

# Run with coverage
pytest --cov=app tests/
```

---

## Configuration

### Development
```python
# config.py
class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///tasks.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
```

### Testing
```python
class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
```

### Environment Variables
```bash
# Override database location
export DATABASE_URL='sqlite:////path/to/tasks.db'
```

---

## Running the Application

### Development Mode
```bash
python run.py
```

API will be available at `http://localhost:5000`

### Production Mode
For production, use a WSGI server:

```bash
# Using gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app

# Using waitress
waitress-serve --port=5000 run:app
```

---

## Database Initialization

The database is automatically created when the app starts:

```python
from app import create_app, db

app = create_app()
with app.app_context():
    db.create_all()  # Creates tables
```

Database file location: `tasks.db` in the current directory

---

## Example Usage Scenarios

### Scenario 1: Complete Task Management Workflow

```bash
# 1. Create a new task
TASK_ID=$(curl -s -X POST http://localhost:5000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Build API",
    "description": "Implement REST endpoints",
    "priority": "high",
    "due_date": "2024-12-31T23:59:59"
  }' | jq '.id')

echo "Created task: $TASK_ID"

# 2. Get task details
curl http://localhost:5000/api/tasks/$TASK_ID | jq .

# 3. Start working on it
curl -X PATCH http://localhost:5000/api/tasks/$TASK_ID/status \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'

# 4. Mark as complete
curl -X PATCH http://localhost:5000/api/tasks/$TASK_ID/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'

# 5. View stats
curl http://localhost:5000/api/tasks/stats | jq .
```

### Scenario 2: Bulk Task Management

```bash
# Create multiple tasks
for i in {1..5}; do
  curl -s -X POST http://localhost:5000/api/tasks \
    -H "Content-Type: application/json" \
    -d "{\"title\": \"Task $i\", \"priority\": \"medium\"}"
done

# Get first page of tasks
curl "http://localhost:5000/api/tasks?page=1&per_page=10" | jq .

# Get high priority tasks
curl "http://localhost:5000/api/tasks?priority=high" | jq .

# Search tasks
curl "http://localhost:5000/api/tasks/search?q=API" | jq .
```

---

## Performance Considerations

1. **Pagination** - Always paginate list endpoints to avoid loading large datasets
2. **Indexing** - Database is optimized for common queries (status, priority)
3. **Connection Pooling** - Handled automatically by SQLAlchemy
4. **Caching** - Can be added at application level for stats

---

## Security Notes

1. **Input Validation** - All inputs validated before database operations
2. **SQL Injection** - Protected by SQLAlchemy ORM
3. **CORS** - Not configured (add flask-cors for frontend integration)
4. **Authentication** - Not implemented (add flask-jwt-extended for auth)
5. **Rate Limiting** - Not implemented (add flask-limiter for production)

For production deployment:
- Add authentication/authorization
- Enable CORS if needed
- Add rate limiting
- Use environment-based configuration
- Deploy with production WSGI server
- Enable HTTPS

---

## License

Built as a demonstration of production-ready Flask API development patterns.
