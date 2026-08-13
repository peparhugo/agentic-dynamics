"""
Flask Task Management API with SQLAlchemy and SQLite storage.
Features proper connection pooling and error handling.
"""

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
import os

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///tasks.db")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "poolclass": QueuePool,
    "pool_size": 20,
    "max_overflow": 10,
}

db = SQLAlchemy(app)


# ── Models ────────────────────────────────────────────────────

class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def init_db():
    with app.app_context():
        db.create_all()


# ── Routes ─────────────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
def list_tasks():
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    return jsonify([task.to_dict() for task in tasks])


@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip() if data.get("title") else ""

    if not title:
        return jsonify({"error": "title is required"}), 400

    task = Task(title=title, status="pending")
    db.session.add(task)
    db.session.commit()

    return jsonify(task.to_dict()), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
def show_task(task_id: int):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task.to_dict())


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def edit_task(task_id: int):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data and data["title"]:
        task.title = data["title"].strip()

    if "status" in data and data["status"]:
        task.status = data["status"]

    db.session.commit()
    return jsonify(task.to_dict())


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
