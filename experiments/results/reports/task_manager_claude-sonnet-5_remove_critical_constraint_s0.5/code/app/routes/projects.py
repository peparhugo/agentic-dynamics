from flask import Blueprint, jsonify, request

from .. import repository
from ..errors import NotFoundError
from ..schemas import validate_project_payload

projects_bp = Blueprint("projects", __name__, url_prefix="/api/projects")


def _get_project_or_404(project_id):
    project = repository.get_project(project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} not found")
    return project


@projects_bp.get("")
def list_projects():
    return jsonify(repository.list_projects())


@projects_bp.post("")
def create_project():
    payload = request.get_json(silent=True) or {}
    data = validate_project_payload(payload)
    project = repository.create_project(data["name"], data.get("description", ""))
    return jsonify(project), 201


@projects_bp.get("/<int:project_id>")
def get_project(project_id):
    return jsonify(_get_project_or_404(project_id))


@projects_bp.put("/<int:project_id>")
def update_project(project_id):
    _get_project_or_404(project_id)
    payload = request.get_json(silent=True) or {}
    data = validate_project_payload(payload, partial=True)
    project = repository.update_project(project_id, data)
    return jsonify(project)


@projects_bp.delete("/<int:project_id>")
def delete_project(project_id):
    _get_project_or_404(project_id)
    repository.delete_project(project_id)
    return "", 204
