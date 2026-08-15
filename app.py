"""Flask API for task management.

Storage is flat-file (JSON), not a database — see storage.py.
"""

from flask import Flask, jsonify, request

import storage


def create_app():
    app = Flask(__name__)
    storage.init_storage()

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.route("/tasks", methods=["POST"])
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        task = storage.create_task(title.strip())
        return jsonify(task), 201

    @app.route("/tasks", methods=["GET"])
    def list_tasks():
        return jsonify(storage.list_tasks()), 200

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    def get_task(task_id):
        task = storage.get_task(task_id)
        if task is None:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task), 200

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    def update_task(task_id):
        if storage.get_task(task_id) is None:
            return jsonify({"error": "Task not found"}), 404

        data = request.get_json(silent=True) or {}
        has_title = "title" in data
        has_status = "status" in data
        if not has_title and not has_status:
            return jsonify({"error": "title or status is required"}), 400

        title = data.get("title")
        if has_title and (not isinstance(title, str) or not title.strip()):
            return jsonify({"error": "title must be a non-empty string"}), 400

        status = data.get("status")
        if has_status and (not isinstance(status, str) or not status.strip()):
            return jsonify({"error": "status must be a non-empty string"}), 400

        task = storage.update_task(
            task_id,
            title=title.strip() if has_title else None,
            status=status.strip() if has_status else None,
        )
        return jsonify(task), 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
