# JWT Authentication Implementation for Task Management API

## Summary
Successfully added JWT authentication to the task management API with complete user isolation and password security.

## Key Components Implemented

### 1. Database Schema (SQLite)
- **users table**: id, username (unique), password_hash, created_at
- **tokens table**: token (PK), user_id (FK), expires_at
- **tasks table**: Added user_id (FK) to associate tasks with users

### 2. Authentication Endpoints
- **POST /auth/register** — Create new user account
  - Required: username, password (min 8 chars)
  - Returns: 201 with user info, 409 if username exists, 400 for invalid input
  
- **POST /auth/login** — Authenticate and get JWT token
  - Required: username, password
  - Returns: 200 with token, 401 for invalid credentials, 400 for missing input

### 3. Protected Task Endpoints
All task endpoints now require `Authorization: Bearer <token>` header:
- **POST /tasks** — Create task (auth required)
- **GET /tasks** — List user's own tasks (auth required)
- **GET /tasks/{id}** — Get specific task (auth required, ownership validated)
- **PUT /tasks/{id}** — Update task (auth required, ownership validated)

### 4. Security Features
- **Password Hashing**: werkzeug.security.generate_password_hash/check_password_hash (bcrypt-based)
- **Token Storage**: Stored in database with expiration (default: 3600 seconds)
- **User Isolation**: Each user only sees and can modify their own tasks
- **Token Validation**: Checks token existence and expiration

### 5. Authorization Decorator
`@require_auth` decorator:
- Validates `Authorization: Bearer <token>` header
- Retrieves user from valid token
- Returns 401 for missing/invalid/expired tokens
- Passes authenticated user to route handler

## Test Coverage
39 comprehensive tests including:
- ✅ User registration (success, validation, duplicates)
- ✅ User login (success, invalid credentials)
- ✅ Task CRUD with authentication
- ✅ User isolation (users see only their tasks)
- ✅ Authorization enforcement (401 for missing tokens)
- ✅ Ownership validation (404 for accessing other users' tasks)
- ✅ Token expiration
- ✅ Integration workflows with multiple users

## Environment Variables
- `DATABASE` — SQLite database path (default: "tasks.db")
- `SECRET_KEY` — Flask secret key (auto-generated if not set)
- `TOKEN_TTL` — Token expiration time in seconds (default: 3600)

## Migration Strategy
Existing tasks table:
- Old schema used `id` as PK, no owner
- New schema adds `user_id` FK and AUTOINCREMENT
- Schema created fresh with CREATE TABLE IF NOT EXISTS
- Backward compatible: new schema is independent

## All Tests Passing
```
39 passed in 9.07s ✅
```
