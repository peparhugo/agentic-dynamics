"""API v1: Note CRUD with pagination, plus admin audit-log access."""
from flask import Blueprint, g, jsonify

from ...audit import audit
from ...auth.jwt_utils import admin_required, auth_required
from ...errors import NotFoundError
from ...extensions import db
from ...models import AuditLog, Note
from ...pagination import paginate
from ...rate_limit import rate_limit
from ...validation import String, validate_json

api_v1 = Blueprint("api_v1", __name__)

NOTE_CREATE_SCHEMA = {
    "title": String(min_length=1, max_length=200),
    "body": String(required=False, default="", max_length=10_000),
}
NOTE_UPDATE_SCHEMA = {
    "title": String(required=False, min_length=1, max_length=200),
    "body": String(required=False, max_length=10_000),
}


def _get_owned_note(note_id: int) -> Note:
    note = Note.query.filter_by(id=note_id, owner_id=g.current_user.id).first()
    if note is None:
        raise NotFoundError("Note not found.")
    return note


@api_v1.get("/notes")
@auth_required
@rate_limit()
def list_notes():
    query = (Note.query.filter_by(owner_id=g.current_user.id)
             .order_by(Note.id.asc()))
    return jsonify(paginate(query))


@api_v1.post("/notes")
@auth_required
@rate_limit()
def create_note():
    data = validate_json(NOTE_CREATE_SCHEMA)
    note = Note(owner_id=g.current_user.id, **data)
    db.session.add(note)
    db.session.flush()
    audit("note.create", resource_type="note", resource_id=note.id, status_code=201)
    db.session.commit()
    return jsonify({"data": note.to_dict()}), 201


@api_v1.get("/notes/<int:note_id>")
@auth_required
@rate_limit()
def get_note(note_id: int):
    return jsonify({"data": _get_owned_note(note_id).to_dict()})


@api_v1.patch("/notes/<int:note_id>")
@auth_required
@rate_limit()
def update_note(note_id: int):
    note = _get_owned_note(note_id)
    data = validate_json(NOTE_UPDATE_SCHEMA)
    for field, value in data.items():
        setattr(note, field, value)
    audit("note.update", resource_type="note", resource_id=note.id,
          status_code=200, detail=f"fields={sorted(data)}")
    db.session.commit()
    return jsonify({"data": note.to_dict()})


@api_v1.delete("/notes/<int:note_id>")
@auth_required
@rate_limit()
def delete_note(note_id: int):
    note = _get_owned_note(note_id)
    db.session.delete(note)
    audit("note.delete", resource_type="note", resource_id=note_id, status_code=204)
    db.session.commit()
    return "", 204


@api_v1.get("/audit-logs")
@admin_required
@rate_limit()
def list_audit_logs():
    query = AuditLog.query.order_by(AuditLog.id.desc())
    return jsonify(paginate(query))
