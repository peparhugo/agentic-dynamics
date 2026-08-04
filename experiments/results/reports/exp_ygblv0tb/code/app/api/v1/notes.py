from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ...audit import record_audit
from ...errors import ApiError
from ...extensions import db
from ...models import Note
from ...pagination import paginate
from ...schemas import NoteCreateSchema, NoteUpdateSchema
from . import api_v1


def _current_user_id():
    return int(get_jwt_identity())


def _json_body():
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError("Request body must be valid JSON", 400)
    return data


def _get_owned_note(note_id):
    note = db.session.get(Note, note_id)
    if note is None:
        raise ApiError("Note not found", 404)
    if note.user_id != _current_user_id():
        # Do not leak existence of other users' notes.
        raise ApiError("Note not found", 404)
    return note


@api_v1.get("/notes")
@jwt_required()
def list_notes():
    query = (Note.query
             .filter_by(user_id=_current_user_id())
             .order_by(Note.created_at.desc(), Note.id.desc()))
    return jsonify(paginate(query))


@api_v1.post("/notes")
@jwt_required()
def create_note():
    data = NoteCreateSchema().load(_json_body())
    note = Note(user_id=_current_user_id(), **data)
    db.session.add(note)
    db.session.commit()
    record_audit("note.create", 201, user_id=note.user_id,
                 detail=f"note_id={note.id}")
    return jsonify({"note": note.to_dict()}), 201


@api_v1.get("/notes/<int:note_id>")
@jwt_required()
def get_note(note_id):
    note = _get_owned_note(note_id)
    return jsonify({"note": note.to_dict()})


@api_v1.patch("/notes/<int:note_id>")
@jwt_required()
def update_note(note_id):
    note = _get_owned_note(note_id)
    data = NoteUpdateSchema().load(_json_body())
    if not data:
        raise ApiError("No updatable fields provided", 400)
    for key, value in data.items():
        setattr(note, key, value)
    db.session.commit()
    record_audit("note.update", 200, user_id=note.user_id,
                 detail=f"note_id={note.id} fields={sorted(data)}")
    return jsonify({"note": note.to_dict()})


@api_v1.delete("/notes/<int:note_id>")
@jwt_required()
def delete_note(note_id):
    note = _get_owned_note(note_id)
    user_id = note.user_id
    db.session.delete(note)
    db.session.commit()
    record_audit("note.delete", 204, user_id=user_id,
                 detail=f"note_id={note_id}")
    return "", 204
