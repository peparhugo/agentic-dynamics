"""
Task Management Flask API using flat-file storage (JSON).
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
from pathlib import Path

app = Flask(__name__)

# Storage configuration
STORAGE_DIR = os.environ.get("STORAGE_DIR", "./data")
TASKS_FILE = os.path.join(STORAGE_DIR, "tasks.json")


# ── Storage Layer ────────────────────────────────────────────────

def _ensure_storage():
    """Ensure storage directory and file exist."""
    Path(STORAGE_DIR).mkdir(parents=True, exist_ok=True)
    if not os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, 'w') as f:
            json.dump([], f)


def _load_tasks():
    """Load all tasks from JSON file."""
    _ensure_storage()
    try:
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_tasks(tasks):
    """Save all tasks to JSON file."""
    _ensure_storage()
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)


def _get_next_id():
    """Get the next auto-increment ID."""
    tasks = _load_tasks()
    if not tasks:
        return 1
    return max(t['id'] for t in tasks) + 1


# ── Endpoints ────────────────────────────────────────────────────

@app.route('/tasks', methods=['POST'])
def create_task():
    """Create a new task. Expects JSON: {title: str}"""
    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()

    if not title:
        return jsonify({"error": "missing title"}), 400

    tasks = _load_tasks()
    new_task = {
        'id': _get_next_id(),
        'title': title,
        'status': 'pending',
        'created_at': datetime.utcnow().isoformat()
    }
    tasks.append(new_task)
    _save_tasks(tasks)

    return jsonify(new_task), 201


@app.route('/tasks', methods=['GET'])
def list_tasks():
    """List all tasks ordered by created_at descending."""
    tasks = _load_tasks()
    # Sort by created_at descending
    sorted_tasks = sorted(tasks, key=lambda x: x['created_at'], reverse=True)
    return jsonify(sorted_tasks)


@app.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get a single task by ID."""
    tasks = _load_tasks()
    task = next((t for t in tasks if t['id'] == task_id), None)

    if task is None:
        return jsonify({"error": "task not found"}), 404

    return jsonify(task)


@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """Update task title and/or status."""
    data = request.get_json(silent=True) or {}
    tasks = _load_tasks()
    task = next((t for t in tasks if t['id'] == task_id), None)

    if task is None:
        return jsonify({"error": "task not found"}), 404

    # Update title if provided
    if 'title' in data:
        title = data['title'].strip()
        if title:
            task['title'] = title

    # Update status if provided
    if 'status' in data:
        task['status'] = data['status']

    _save_tasks(tasks)
    return jsonify(task)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    _ensure_storage()
    app.run(debug=True)
