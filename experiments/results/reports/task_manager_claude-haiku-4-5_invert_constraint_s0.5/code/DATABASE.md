# Database Schema Documentation

## Overview

The Task Management API uses SQLite with SQLAlchemy ORM. The database automatically creates tables on first run through the `@app.before_request` decorator that calls `db.create_all()`.

## Entity Relationship Diagram

```
┌─────────────┐
│   Users     │
├─────────────┤
│ id (PK)     │◄──┐
│ username    │   │
│ email       │   │
│ password_hash│  │
│ created_at  │   │
│ updated_at  │   │
└─────────────┘   │
       ▲          │
       │          │
    ┌──┘──────┐   │
    │         │   │
    │         │   │
    │     ┌────────────────────────┐
    │     │   Tasks                │
    │     ├────────────────────────┤
    │     │ id (PK)                │
    │     │ title                  │
    │     │ description            │
    │     │ status                 │
    │     │ priority               │
    │     │ owner_id (FK) ─────────┼────── (owner)
    │     │ assigned_to_id (FK) ───┼────── (assignee)
    │     │ category_id (FK) ──┐   │
    │     │ due_date           │   │
    │     │ created_at         │   │
    │     │ updated_at         │   │
    │     └────────────────────┼───┘
    │                          │
    │     ┌────────────────────┘
    │     │
    │  ┌──▼──────────┐
    │  │ Categories  │
    │  ├─────────────┤
    │  │ id (PK)     │
    │  │ name        │
    │  │ description │
    │  │ created_at  │
    │  └─────────────┘
    │
    └─────────────────────────────────────────
```

## Tables

### users

Stores user account information.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | User ID |
| username | VARCHAR(80) | UNIQUE, NOT NULL, INDEX | Unique username |
| email | VARCHAR(120) | UNIQUE, NOT NULL, INDEX | Email address |
| password_hash | VARCHAR(255) | NOT NULL | SHA-256 hashed password |
| created_at | DATETIME | DEFAULT NOW | Account creation time |
| updated_at | DATETIME | DEFAULT NOW, ON UPDATE NOW | Last update time |

**Relationships:**
- Has many Tasks (owner_id)
- Has many Tasks (assigned_to_id)

**Indices:**
- username (unique)
- email (unique)

### categories

Task categories for organization.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | Category ID |
| name | VARCHAR(50) | UNIQUE, NOT NULL, INDEX | Category name |
| description | TEXT | NULL | Description |
| created_at | DATETIME | DEFAULT NOW | Creation time |

**Relationships:**
- Has many Tasks (category_id)

**Indices:**
- name (unique)

### tasks

Core task data.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | Task ID |
| title | VARCHAR(255) | NOT NULL, INDEX | Task title |
| description | TEXT | NULL | Task description |
| status | VARCHAR(20) | NOT NULL, INDEX, DEFAULT 'pending' | Current status |
| priority | VARCHAR(20) | NOT NULL, INDEX, DEFAULT 'medium' | Task priority |
| owner_id | INTEGER | NOT NULL, INDEX, FOREIGN KEY | User who created task |
| category_id | INTEGER | NULL, INDEX, FOREIGN KEY | Task category |
| assigned_to_id | INTEGER | NULL, INDEX, FOREIGN KEY | User assigned to task |
| due_date | DATETIME | NULL, INDEX | Task due date |
| created_at | DATETIME | DEFAULT NOW, INDEX | Creation time |
| updated_at | DATETIME | DEFAULT NOW, ON UPDATE NOW | Last update time |

**Relationships:**
- Belongs to User (owner_id) - "owner"
- Belongs to User (assigned_to_id) - "assignee"
- Belongs to Category (category_id)

**Indices:**
- title
- status
- priority
- owner_id
- category_id
- assigned_to_id
- due_date
- created_at

**Enums:**
- status: pending, in_progress, completed, cancelled
- priority: low, medium, high, urgent

## Data Types

### SQLite Type Mapping
- `INTEGER` - Whole numbers
- `VARCHAR(n)` - Strings with max length
- `TEXT` - Longer text fields
- `DATETIME` - Timestamps stored as ISO 8601 strings

### Python Enum Types

**TaskStatus**
```python
class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
```

**TaskPriority**
```python
class TaskPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
```

## Constraints

### Primary Keys
All tables use auto-incrementing INTEGER primary keys.

### Foreign Keys
- `tasks.owner_id` → `users.id` (no cascade)
- `tasks.assigned_to_id` → `users.id` (no cascade)
- `tasks.category_id` → `categories.id` (no cascade)

### Unique Constraints
- `users.username`
- `users.email`
- `categories.name`

### Not Null Constraints
- `users.username`, `users.email`, `users.password_hash`
- `categories.name`
- `tasks.title`, `tasks.owner_id`

### Default Values
- `tasks.status` = 'pending'
- `tasks.priority` = 'medium'
- Timestamps default to current UTC time

## Indexes

Indexes are automatically created for:
- All primary keys
- All foreign keys
- All unique constraints
- Frequently queried columns: title, status, priority, owner_id, category_id, assigned_to_id, due_date

## Database Initialization

The database is automatically initialized when the application starts:

```python
@app.before_request
def create_tables():
    db.create_all()
```

This creates all tables if they don't exist. It's safe to run multiple times.

To manually create tables:

```python
from app import app, db
with app.app_context():
    db.create_all()
```

## Database File

SQLite database file location:
```
./tasks.db
```

## Queries

### Find all tasks for a user
```python
user_tasks = Task.query.filter_by(owner_id=user_id).all()
```

### Find tasks assigned to a user
```python
assigned_tasks = Task.query.filter_by(assigned_to_id=user_id).all()
```

### Find tasks by status
```python
completed = Task.query.filter_by(status='completed').all()
```

### Search tasks
```python
results = Task.query.filter(
    Task.title.ilike('%keyword%') | 
    Task.description.ilike('%keyword%')
).all()
```

### Filter by multiple criteria
```python
tasks = Task.query.filter_by(
    owner_id=user_id,
    status='in_progress',
    priority='high'
).all()
```

### Get paginated results
```python
page = Task.query.paginate(page=1, per_page=10)
tasks = page.items
total = page.total
pages = page.pages
```

## Performance Considerations

1. **Indexes**: Most frequently queried columns have indexes
2. **Foreign Keys**: Use integer IDs which are efficient
3. **Pagination**: Large result sets should be paginated
4. **Search**: Full-text search uses LIKE which is adequate for small-medium datasets
5. **Joins**: SQLAlchemy lazy loads relationships by default

For very large datasets (millions of records), consider:
- Adding full-text search engine (Elasticsearch, PostgreSQL FTS)
- Archiving old tasks
- Partitioning by date
- Upgrading to PostgreSQL

## Backup and Recovery

SQLite database is a single file, making it easy to backup:

```bash
# Backup
cp tasks.db tasks.db.backup

# Restore
cp tasks.db.backup tasks.db
```

For production, consider:
- Regular automated backups
- Replication to another database
- Migration to PostgreSQL
- Logical backups with timestamps
