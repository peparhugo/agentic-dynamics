# Task Management API

A complete REST API for task management built with Flask and SQLite.

## Features

- Create, read, update, and delete tasks
- Filter tasks by status and priority
- Search tasks by title and description
- Track task completion timestamps
- Task statistics endpoint
- Full input validation
- Comprehensive error handling
- Pagination support

## Project Structure

```
├── app/
│   ├── __init__.py       # Flask app factory
│   ├── models.py         # SQLAlchemy models
│   └── routes.py         # API endpoints
├── tests/
│   └── test_api.py       # Comprehensive test suite
├── config.py             # Configuration
├── run.py                # Application entry point
└── requirements.txt      # Dependencies
```

## Installation

```bash
pip install -r requirements.txt
```

## Running the Application

```bash
python run.py
```

The API will be available at `http://localhost:5000/api/tasks`

## Running Tests

```bash
pytest
pytest -v --cov=app  # With coverage
```

## API Endpoints

### Tasks Management

- `GET /api/tasks` - List all tasks (with pagination, filtering)
- `POST /api/tasks` - Create a new task
- `GET /api/tasks/<id>` - Get a specific task
- `PUT /api/tasks/<id>` - Update a task
- `DELETE /api/tasks/<id>` - Delete a task
- `PATCH /api/tasks/<id>/status` - Update task status

### Search & Stats

- `GET /api/tasks/search?q=query` - Search tasks
- `GET /api/tasks/stats` - Get task statistics

## Task Model

```json
{
  "id": 1,
  "title": "Task Title",
  "description": "Optional description",
  "status": "pending|in_progress|completed|cancelled",
  "priority": "low|medium|high",
  "due_date": "2024-12-31T23:59:59",
  "completed_at": "2024-12-25T12:00:00",
  "created_at": "2024-12-01T00:00:00",
  "updated_at": "2024-12-15T00:00:00"
}
```

## Example Usage

### Create a task

```bash
curl -X POST http://localhost:5000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Complete project",
    "description": "Finish the task management API",
    "priority": "high"
  }'
```

### Get all tasks

```bash
curl http://localhost:5000/api/tasks
```

### Update a task

```bash
curl -X PUT http://localhost:5000/api/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

### Search tasks

```bash
curl "http://localhost:5000/api/tasks/search?q=project"
```
