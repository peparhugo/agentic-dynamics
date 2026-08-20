"""Built-in story catalog — the three shipped multi-session stories.

Extracted from ``runtime/story.py`` (refactor-repair Debt-1). Each ``*_story()`` returns a
``StoryConfig``; ``BUILTIN_STORIES`` indexes them by their CLI name.
"""
from __future__ import annotations

from agentic_dynamics.runtime.story.models import SessionSpec, StoryConfig


def task_manager_story() -> StoryConfig:
    """A 5-session story building a task management API.

    Session 1: Core models + CRUD (greenfield)
    Session 2: JWT authentication (feature addition)
    Session 3: Async notification worker (integration)
    Session 4: Repository pattern refactor (refactor)
    Session 5: Rate limiting + pagination (cross-cutting)
    """
    return StoryConfig(
        name="task_manager_api",
        description="Build a task management API across 5 sessions",
        language="python",
        constraints=[
            "All endpoints return JSON",
            "Use SQLite for persistence",
            "Include error handling for all endpoints",
        ],
        sessions=[
            SessionSpec(
                session_number=1,
                task_type="greenfield",
                description="Core models and CRUD endpoints",
                prompt=(
                    "Create a Flask API for task management with the following requirements:\n\n"
                    "MODELS:\n"
                    "- Task: id (int, auto), title (str), status (str, default 'pending'), "
                    "created_at (datetime)\n\n"
                    "ENDPOINTS:\n"
                    "- POST /tasks — create a task (JSON body: {title: str})\n"
                    "- GET /tasks — list all tasks ordered by created_at desc\n"
                    "- GET /tasks/{id} — get a single task\n"
                    "- PUT /tasks/{id} — update task title and/or status\n\n"
                    "STORAGE:\n"
                    "- Use SQLite. Initialize the schema on startup.\n\n"
                    "ERROR HANDLING:\n"
                    "- Return 400 for missing title on POST\n"
                    "- Return 404 when task not found\n"
                    "- Return proper JSON error messages\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=2,
                task_type="feature_addition",
                description="JWT authentication middleware",
                prompt=(
                    "Add JWT authentication to the existing task management API.\n\n"
                    "NEW MODEL:\n"
                    "- User: id (int, auto), username (str, unique), password_hash (str)\n\n"
                    "NEW ENDPOINTS:\n"
                    "- POST /auth/register — create user (JSON: {username, password})\n"
                    "- POST /auth/login — return JWT token (JSON: {username, password})\n\n"
                    "PROTECT EXISTING ENDPOINTS:\n"
                    "- All /tasks/* endpoints require a valid JWT in Authorization header\n"
                    "- Return 401 for missing/invalid tokens\n"
                    "- Each user sees only their own tasks\n\n"
                    "SECURITY:\n"
                    "- Hash passwords with bcrypt or werkzeug\n"
                    "- Add a Task.owner_id field to associate tasks with users\n"
                    "- Add a migration step that doesn't break existing data\n\n"
                    "Write ALL code. Update existing tests. Add auth tests. "
                    "Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=3,
                task_type="integration",
                description="Async notification worker integration",
                prompt=(
                    "Add an async email notification system to the task management API.\n\n"
                    "REQUIREMENT:\n"
                    "When a task's status changes to 'completed', send a notification email "
                    "to the task owner asynchronously (do not block the API response).\n\n"
                    "IMPLEMENTATION:\n"
                    "- Use Celery with Redis as the message broker\n"
                    "- Create a Celery task: send_notification_email(user_email, task_title)\n"
                    "- Trigger the Celery task from the PUT /tasks/{id} endpoint when "
                    "status changes to 'completed'\n"
                    "- The email sending can be a mock (print to console or log)\n"
                    "- Add a celery_config.py with broker URL, result backend, task routes\n\n"
                    "DO NOT BREAK existing endpoints or auth. Keep all existing tests passing.\n"
                    "Add tests for the notification trigger logic.\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=4,
                task_type="refactor",
                description="Repository pattern refactor",
                prompt=(
                    "Refactor the data access layer to use the Repository pattern.\n\n"
                    "REQUIREMENT:\n"
                    "Extract all database operations into repository classes. "
                    "The API routes should NOT directly access SQLite.\n\n"
                    "IMPLEMENTATION:\n"
                    "- Create a BaseRepository abstract class with common CRUD operations\n"
                    "- Create TaskRepository that extends BaseRepository\n"
                    "- Create UserRepository that extends BaseRepository\n"
                    "- Move ALL SQL queries out of route handlers into repositories\n"
                    "- Route handlers should call repository methods, not raw SQL\n"
                    "- The external API behavior MUST remain identical (same responses)\n"
                    "- All existing tests MUST pass without modification\n\n"
                    "This is a pure refactor. Do NOT add new features or change API behavior.\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=5,
                task_type="cross_cutting",
                description="Rate limiting and cursor-based pagination",
                prompt=(
                    "Add rate limiting and pagination to the task management API.\n\n"
                    "RATE LIMITING:\n"
                    "- Limit each authenticated user to 100 requests per minute\n"
                    "- Use Flask-Limiter with Redis as the storage backend\n"
                    "- Return 429 with Retry-After header when limit exceeded\n"
                    "- Apply rate limiting to ALL endpoints including auth\n\n"
                    "PAGINATION:\n"
                    "- Replace GET /tasks (return all) with cursor-based pagination\n"
                    "- Query params: ?cursor=<id>&limit=<n> (default limit=20, max=100)\n"
                    "- Response format: {data: [...], next_cursor: str|null, total: int}\n"
                    "- Cursor is the id of the last item in the current page\n"
                    "- GET /tasks without cursor returns the first page\n\n"
                    "DO NOT BREAK existing functionality. Keep auth and repository pattern intact.\n"
                    "Write pytest tests for rate limiting and pagination.\n"
                    "Focus on a working implementation — skip optimization."
                ),
            ),
        ],
    )


def static_site_gen_story() -> StoryConfig:
    """A 5-session story building a static site generator in TypeScript.

    Session 1: Markdown parsing + HTML rendering (greenfield)
    Session 2: Template engine + layout support (feature addition)
    Session 3: Live reload dev server (integration)
    Session 4: Plugin system refactor (refactor)
    Session 5: Incremental builds + caching (cross-cutting)
    """
    return StoryConfig(
        name="static_site_gen",
        description="Build a static site generator CLI across 5 sessions",
        language="typescript",
        constraints=[
            "All output goes to ./dist by default",
            "CLI interface via commander or yargs",
            "TypeScript with strict mode enabled",
        ],
        sessions=[
            SessionSpec(
                session_number=1,
                task_type="greenfield",
                description="Markdown parsing and HTML rendering",
                prompt=(
                    "Build a static site generator CLI in TypeScript.\n\n"
                    "CORE FEATURES:\n"
                    "- Read Markdown files from a content directory (default: ./content)\n"
                    "- Parse Markdown to HTML with frontmatter support (title, date, tags)\n"
                    "- Generate an index.html listing all pages\n"
                    "- Each page gets its own HTML file in ./dist\n\n"
                    "CLI:\n"
                    "- npx ssg build — generate the site\n"
                    "- Options: --content <dir>, --output <dir>\n\n"
                    "TECH:\n"
                    "- TypeScript with strict mode\n"
                    "- Use marked or markdown-it for parsing\n"
                    "- Use gray-matter for frontmatter\n"
                    "- Tests with jest\n\n"
                    "Write ALL code. Run jest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=2,
                task_type="feature_addition",
                description="Template engine and layout support",
                prompt=(
                    "Add template engine and layout support to the static site generator.\n\n"
                    "TEMPLATES:\n"
                    "- Support Handlebars (.hbs) or EJS templates\n"
                    "- Each page can specify a template in its frontmatter\n"
                    "- Default template if none specified\n"
                    "- Layout templates with {{{body}}} placeholder for page content\n"
                    "- Support partials/includes (header, footer, nav)\n\n"
                    "DIRECTORY STRUCTURE:\n"
                    "- ./templates/ — template files\n"
                    "- ./templates/layouts/ — layout templates\n"
                    "- ./templates/partials/ — reusable partials\n\n"
                    "EXISTING FUNCTIONALITY must continue working.\n"
                    "Update tests. Add template-specific tests.\n\n"
                    "Write ALL code. Run jest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=3,
                task_type="integration",
                description="Live reload development server",
                prompt=(
                    "Add a live-reload development server to the SSG.\n\n"
                    "DEV SERVER:\n"
                    "- npx ssg serve — start dev server on localhost:3000\n"
                    "- Watch content/ and templates/ directories for changes\n"
                    "- Rebuild on file change\n"
                    "- Inject a WebSocket script into served pages for live reload\n"
                    "- Reload browser automatically when rebuild completes\n\n"
                    "TECH:\n"
                    "- Use chokidar for file watching\n"
                    "- Use ws or socket.io for WebSocket\n"
                    "- Serve from ./dist directory\n"
                    "- Add --port option to serve command\n\n"
                    "DO NOT BREAK the build command. Keep all existing tests passing.\n\n"
                    "Write ALL code. Run jest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=4,
                task_type="refactor",
                description="Plugin system architecture",
                prompt=(
                    "Refactor the SSG to use a plugin system for extensibility.\n\n"
                    "PLUGIN SYSTEM:\n"
                    "- Define a Plugin interface with lifecycle hooks:\n"
                    "  - onStart(), beforeBuild(), afterBuild(), onFile(page), onEnd()\n"
                    "- Plugins are TypeScript modules in ./plugins/\n"
                    "- Load plugins from a config file (ssg.config.ts)\n"
                    "- Plugin pipeline: each hook runs all plugin hooks in order\n"
                    "- Existing features (markdown, templates, live reload) become built-in plugins\n\n"
                    "REFACTOR:\n"
                    "- Extract markdown parsing into MarkdownPlugin\n"
                    "- Extract template rendering into TemplatePlugin\n"
                    "- Extract dev server into DevServerPlugin\n"
                    "- The core SSG engine orchestrates the plugin pipeline\n"
                    "- External API behavior MUST remain identical\n\n"
                    "Write ALL code. Run jest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=5,
                task_type="cross_cutting",
                description="Incremental builds and content caching",
                prompt=(
                    "Add incremental builds and caching to the SSG.\n\n"
                    "INCREMENTAL BUILDS:\n"
                    "- npx ssg build --incremental — only rebuild changed pages\n"
                    "- Track file hashes in a .ssg-cache.json manifest\n"
                    "- Skip rebuild of pages whose source and template haven't changed\n"
                    "- Clean build if cache is missing or --clean flag is passed\n\n"
                    "CACHING:\n"
                    "- Cache rendered HTML in memory or on disk\n"
                    "- Cache parsed frontmatter\n"
                    "- Invalidate cache entries when source or template changes\n"
                    "- Report build stats: pages built, pages skipped, time saved\n\n"
                    "DO NOT BREAK existing functionality. Keep plugin architecture intact.\n"
                    "Write jest tests for incremental build correctness. Focus on working implementation."
                    "Write ALL code. Run jest. Fix failures until all tests pass."
                ),
            ),
        ],
    )


def notification_service_story() -> StoryConfig:
    """A 5-session story building a real-time notification delivery service.

    Session 1: Core WebSocket server + client (greenfield)
    Session 2: Channel subscriptions + message routing (feature addition)
    Session 3: Redis pub/sub integration (integration)
    Session 4: Extract protocol layer (refactor)
    Session 5: Rate limiting + message persistence (cross-cutting)
    """
    return StoryConfig(
        name="notification_service",
        description="Build a real-time notification delivery service across 5 sessions",
        language="python",
        constraints=[
            "All communication via WebSocket",
            "Use Redis for pub/sub and rate limiting",
            "SQLite for message persistence",
        ],
        sessions=[
            SessionSpec(
                session_number=1,
                task_type="greenfield",
                description="Core WebSocket server with broadcast",
                prompt=(
                    "Build a WebSocket-based notification server in Python.\n\n"
                    "CORE FEATURES:\n"
                    "- Accept WebSocket connections from clients\n"
                    "- Assign each client a unique ID on connect\n"
                    "- Broadcast a message to ALL connected clients\n"
                    "- Handle client disconnect (clean removal)\n"
                    "- REST endpoint: GET /health — returns connected client count\n\n"
                    "MESSAGE FORMAT:\n"
                    "- All messages are JSON: {type: str, payload: dict, timestamp: str}\n"
                    "- Supported types: 'broadcast', 'direct', 'system'\n\n"
                    "TECH:\n"
                    "- Use websockets library (not Flask-SocketIO)\n"
                    "- Async with asyncio\n"
                    "- Thread-safe client registry\n"
                    "- Tests with pytest + pytest-asyncio\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=2,
                task_type="feature_addition",
                description="Channel subscriptions and targeted routing",
                prompt=(
                    "Add channel-based subscriptions to the notification server.\n\n"
                    "CHANNELS:\n"
                    "- Clients subscribe to named channels (e.g. 'alerts', 'system', 'chat')\n"
                    "- Messages are delivered ONLY to clients subscribed to that channel\n"
                    "- Clients can subscribe/unsubscribe dynamically\n"
                    "- A client can be subscribed to multiple channels\n\n"
                    "MESSAGE TYPES:\n"
                    "- Add 'subscribe' and 'unsubscribe' message types\n"
                    "- Messages with a 'channel' field route only to that channel's subscribers\n"
                    "- Messages without a channel still broadcast to all\n\n"
                    "REST ENDPOINTS:\n"
                    "- GET /channels — list active channels and subscriber counts\n"
                    "- GET /channels/{name}/subscribers — list subscriber IDs\n\n"
                    "DO NOT BREAK existing functionality. All tests must pass.\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=3,
                task_type="integration",
                description="Redis pub/sub message backbone",
                prompt=(
                    "Integrate Redis pub/sub as the message backbone.\n\n"
                    "REDIS INTEGRATION:\n"
                    "- Use Redis pub/sub channels for message distribution\n"
                    "- Server publishes to Redis channel; workers subscribe and deliver\n"
                    "- Multiple server instances can share the same Redis backbone\n"
                    "- Client connection state stored in Redis (survives server restart)\n\n"
                    "PERSISTENCE:\n"
                    "- Store all messages in SQLite for history\n"
                    "- REST endpoint: GET /messages?limit=50&offset=0\n"
                    "- Messages table: id, channel, type, payload, timestamp\n\n"
                    "CONFIG:\n"
                    "- REDIS_URL env var for broker connection\n"
                    "- DATABASE_URL env var for SQLite path\n\n"
                    "DO NOT BREAK existing behavior. All tests must pass.\n"
                    "Add integration tests for Redis pub/sub and message persistence.\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=4,
                task_type="refactor",
                description="Extract protocol layer into pluggable transports",
                prompt=(
                    "Refactor the notification server to use a pluggable transport layer.\n\n"
                    "REQUIREMENT:\n"
                    "Extract the WebSocket transport behind a Transport interface so\n"
                    "different transport mechanisms (SSE, polling, raw TCP) can be added\n"
                    "without modifying the core notification logic.\n\n"
                    "IMPLEMENTATION:\n"
                    "- Create BaseTransport abstract class:\n"
                    "  - on_connect(), on_disconnect(), send_message(), broadcast()\n"
                    "- Move WebSocket logic into WebSocketTransport\n"
                    "- The core NotificationServer should work with any Transport\n"
                    "- Transport is selected by config (TRANSPORT env var)\n"
                    "- WebSocketTransport is the default\n\n"
                    "API MUST remain identical. All existing tests must pass without\n"
                    "modification. Client behavior must not change.\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=5,
                task_type="cross_cutting",
                description="Rate limiting + persistent message history",
                prompt=(
                    "Add rate limiting and persistent message history.\n\n"
                    "RATE LIMITING:\n"
                    "- Limit each client to 100 messages per minute\n"
                    "- Limits enforced per-client-ID using Redis counters\n"
                    "- Return error message on rate limit exceeded (no drop)\n"
                    "- Configurable via RATE_LIMIT env var\n\n"
                    "MESSAGE HISTORY:\n"
                    "- REST endpoint: GET /history?channel=X&since=ISO_TIMESTAMP&limit=50\n"
                    "- Returns messages for a specific channel/time range\n"
                    "- Paginated with has_more boolean\n"
                    "- Messages returned in chronological order\n\n"
                    "SYSTEM MESSAGE EXPIRY:\n"
                    "- Messages older than 7 days are automatically cleaned up\n"
                    "- Cleanup runs as a background task on server startup\n"
                    "- Configurable via MESSAGE_TTL_DAYS env var\n\n"
                    "DO NOT BREAK existing functionality. Keep transport layer and pub/sub intact.\n"
                    "Write pytest tests for rate limiting and history queries. Focus on working implementation."
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
        ],
    )


BUILTIN_STORIES: dict[str, StoryConfig] = {
    "task_manager_api": task_manager_story(),
    "static_site_gen": static_site_gen_story(),
    "notification_service": notification_service_story(),
}
