from flask import Flask, request, jsonify
from datetime import datetime
import json
import os

app = Flask(__name__)

STORAGE_FILE = 'tasks.json'

def load_tasks():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, 'r') as f:
            return json.load(f)
    return {'tasks': []}

def save_tasks(data):
    with open(STORAGE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_next_id(data):
    if not data['tasks']:
        return 1
    return max(task['id'] for task in data['tasks']) + 1

@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.get_json()

    if not data or 'title' not in data or not data['title']:
        return jsonify({'error': 'Missing title'}), 400

    tasks_data = load_tasks()
    new_task = {
        'id': get_next_id(tasks_data),
        'title': data['title'],
        'status': data.get('status', 'pending'),
        'created_at': datetime.utcnow().isoformat()
    }
    tasks_data['tasks'].append(new_task)
    save_tasks(tasks_data)

    return jsonify(new_task), 201

@app.route('/tasks', methods=['GET'])
def list_tasks():
    tasks_data = load_tasks()
    sorted_tasks = sorted(tasks_data['tasks'], key=lambda x: x['created_at'], reverse=True)
    return jsonify(sorted_tasks), 200

@app.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    tasks_data = load_tasks()
    task = next((t for t in tasks_data['tasks'] if t['id'] == task_id), None)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task), 200

@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    tasks_data = load_tasks()
    task = next((t for t in tasks_data['tasks'] if t['id'] == task_id), None)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json()
    if 'title' in data:
        task['title'] = data['title']
    if 'status' in data:
        task['status'] = data['status']

    save_tasks(tasks_data)
    return jsonify(task), 200

if __name__ == '__main__':
    app.run(debug=True)
