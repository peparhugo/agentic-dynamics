# Task Management API

A complete, production-ready task management API built with Flask, SQLAlchemy, and SQLite.

## Features

✅ **User Management**
- User registration with validation
- JWT-based authentication
- Secure password hashing

✅ **Task Management**
- Full CRUD operations on tasks
- Task status tracking (todo, in_progress, completed, cancelled)
- Due dates with timezone support
- Rich descriptions

✅ **Organization**
- Task categories (user-specific)
- Priority levels (Low, Medium, High, Critical)
- Task assignment to other users
- Task filtering and search

✅ **API Features**
- Pagination with configurable page size (max 100 per page)
- Full-text search across title and description
- Advanced filtering by status, category, priority, and assignee
- Comprehensive error handling
- Request validation

✅ **Testing**
- 48 comprehensive pytest test cases
- Unit tests for models
- Integration tests for all endpoints
- Authentication tests
- Isolation and security tests
- 100% test pass rate

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Create and activate a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

```bash
# Copy example environment variables
cp .env.example .env

# Edit .env with your configuration (optional)
# DATABASE_URL=sqlite:///task_management.db
# JWT_SECRET_KEY=your-secret-key
```

### Running the Application

```bash
# Start the Flask development server
python3 app.py

# The API will be available at http://localhost:5000
```

### Running Tests

```bash
# Run all tests with verbose output
pytest test_app.py -v

# Run with coverage report
pytest test_app.py --cov=. --cov-report=html

# Run specific test class
pytest test_app.py::TestAuth -v

# Run single test
pytest test_app.py::TestAuth::test_login_success -v
```

## API Endpoints

### Authentication

#### Register User
```
POST /auth/register
Content-Type: application/json

{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "securepassword123"
}

Response 201:
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "created_at": "2024-01-15T10:30:00"
  }
}
```

#### Login
```
POST /auth/login
Content-Type: application/json

{
  "username": "john_doe",
  "password": "securepassword123"
}

Response 200:
{
  "message": "Login successful",
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "created_at": "2024-01-15T10:30:00"
  }
}
```

### Tasks

All task endpoints require JWT authentication:
```
Authorization: Bearer <token>
```

#### Create Task
```
POST /tasks
Content-Type: application/json

{
  "title": "Complete project report",
  "description": "Finish the Q1 2024 project report",
  "status": "in_progress",
  "category_id": 1,
  "priority_id": 3,
  "due_date": "2024-02-01T17:00:00",
  "assigned_to": 2
}

Response 201:
{
  "message": "Task created successfully",
  "task": {
    "id": 1,
    "title": "Complete project report",
    "description": "Finish the Q1 2024 project report",
    "status": "in_progress",
    "category": {...},
    "priority": {...},
    "due_date": "2024-02-01T17:00:00",
    "assigned_to": 2,
    "created_by": 1,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  }
}
```

#### Get All Tasks
```
GET /tasks?page=1&per_page=10&status=in_progress&category_id=1&priority_id=3&search=report

Response 200:
{
  "tasks": [...],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total": 42,
    "pages": 5
  }
}
```

Query Parameters:
- `page`: Page number (default: 1)
- `per_page`: Items per page, max 100 (default: 10)
- `status`: Filter by status (todo, in_progress, completed, cancelled)
- `category_id`: Filter by category ID
- `priority_id`: Filter by priority ID
- `assigned_to`: Filter by assigned user ID
- `search`: Full-text search in title and description

#### Get Task by ID
```
GET /tasks/:id

Response 200:
{
  "id": 1,
  "title": "Complete project report",
  ...
}
```

#### Update Task
```
PUT /tasks/:id
Content-Type: application/json

{
  "title": "Complete project report - REVISED",
  "status": "completed",
  "priority_id": 2
}

Response 200:
{
  "message": "Task updated successfully",
  "task": {...}
}
```

#### Delete Task
```
DELETE /tasks/:id

Response 200:
{
  "message": "Task deleted successfully"
}
```

### Categories

#### Get All Categories
```
GET /tasks/categories

Response 200:
[
  {
    "id": 1,
    "name": "Work",
    "user_id": 1,
    "created_at": "2024-01-15T10:30:00"
  }
]
```

#### Create Category
```
POST /tasks/categories
Content-Type: application/json

{
  "name": "Work"
}

Response 201:
{
  "message": "Category created successfully",
  "category": {...}
}
```

#### Update Category
```
PUT /tasks/categories/:id
Content-Type: application/json

{
  "name": "Job"
}

Response 200:
{
  "message": "Category updated successfully",
  "category": {...}
}
```

#### Delete Category
```
DELETE /tasks/categories/:id

Response 200:
{
  "message": "Category deleted successfully"
}
```

### Priorities

#### Get All Priorities
```
GET /tasks/priorities

Response 200:
[
  {"id": 1, "name": "Low", "level": 1},
  {"id": 2, "name": "Medium", "level": 2},
  {"id": 3, "name": "High", "level": 3},
  {"id": 4, "name": "Critical", "level": 4}
]
```

### Health Check

#### Check API Status
```
GET /health

Response 200:
{
  "status": "healthy"
}
```

## Database Schema

### Users
```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username VARCHAR(80) UNIQUE NOT NULL,
  email VARCHAR(120) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

### Categories
```sql
CREATE TABLE categories (
  id INTEGER PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  user_id INTEGER NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE(user_id, name),
  FOREIGN KEY(user_id) REFERENCES users(id)
);
```

### Priorities
```sql
CREATE TABLE priorities (
  id INTEGER PRIMARY KEY,
  name VARCHAR(50) UNIQUE NOT NULL,
  level INTEGER UNIQUE NOT NULL,
  created_at DATETIME NOT NULL
);
```

### Tasks
```sql
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  status ENUM NOT NULL,
  category_id INTEGER,
  priority_id INTEGER,
  due_date DATETIME,
  assigned_to INTEGER,
  created_by INTEGER NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  FOREIGN KEY(category_id) REFERENCES categories(id),
  FOREIGN KEY(priority_id) REFERENCES priorities(id),
  FOREIGN KEY(assigned_to) REFERENCES users(id),
  FOREIGN KEY(created_by) REFERENCES users(id)
);
```

## Error Handling

The API returns appropriate HTTP status codes and error messages:

| Status | Meaning | Example |
|--------|---------|---------|
| 200 | OK | Successful operation |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid input |
| 401 | Unauthorized | Missing/invalid token |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Duplicate username/email |
| 500 | Internal Error | Server error |

Example error response:
```json
{
  "error": "Title is required"
}
```

## Security

✅ **Implemented**
- Password hashing with Werkzeug
- JWT token-based authentication
- User isolation (users can only see/modify their own tasks)
- Input validation
- SQL injection prevention (SQLAlchemy ORM)
- CORS-ready (add flask-cors if needed)

🔐 **Production Checklist**
- [ ] Set strong JWT_SECRET_KEY in production
- [ ] Use HTTPS only
- [ ] Set secure CORS policy
- [ ] Enable CSRF protection if adding HTML frontend
- [ ] Use PostgreSQL instead of SQLite for production
- [ ] Add rate limiting
- [ ] Implement request logging
- [ ] Set up monitoring and alerting

## Deployment

See [DEPLOYMENT_STRATEGY.md](DEPLOYMENT_STRATEGY.md) for detailed deployment instructions.

Quick start:
```bash
# Production
export FLASK_ENV=production
export JWT_SECRET_KEY=<generate-strong-key>
gunicorn -w 4 -b 0.0.0.0:5000 app:create_app()
```

## Project Structure

```
.
├── app.py                    # Flask app factory
├── models.py                 # Database models
├── auth.py                   # Authentication blueprint
├── tasks.py                  # Tasks blueprint
├── config.py                 # Configuration
├── requirements.txt          # Python dependencies
├── test_app.py              # Pytest test suite (48 tests)
├── .env.example             # Environment variables template
├── DEPLOYMENT_STRATEGY.md   # Deployment guide
└── README.md                # This file
```

## Testing

The project includes 48 comprehensive tests covering:

- **Authentication (9 tests)**: Registration, login, token validation
- **Task CRUD (13 tests)**: Create, read, update, delete with validations
- **Filtering (6 tests)**: Pagination, search, status/category/priority filters
- **Categories (7 tests)**: CRUD operations, uniqueness
- **Priorities (3 tests)**: Priority levels, task filtering
- **Task Assignment (3 tests)**: Assigning tasks, filtering by assignee
- **Security (3 tests)**: Token validation, malformed headers
- **Isolation (2 tests)**: User data isolation, access control
- **Health Check (1 test)**: API availability

Run tests:
```bash
pytest test_app.py -v                    # Verbose output
pytest test_app.py --cov                 # With coverage
pytest test_app.py -k "TestAuth"         # Specific class
pytest test_app.py -x --tb=short         # Stop on first failure
```

## Performance

- **Database Indexes**: Created on frequently-queried columns (status, created_at, category_id)
- **Pagination**: Prevents loading entire datasets into memory
- **Lazy Loading**: Relationships loaded on-demand via SQLAlchemy
- **Query Optimization**: Filtered queries at database level

For large deployments (1M+ tasks), consider:
- Upgrading to PostgreSQL
- Adding Redis cache for popular queries
- Implementing database sharding
- Adding full-text search indices

## License

This project is provided as-is for demonstration purposes.

## Support

For issues or questions:
1. Check the test suite for usage examples
2. Review the API endpoints section above
3. See DEPLOYMENT_STRATEGY.md for deployment questions
