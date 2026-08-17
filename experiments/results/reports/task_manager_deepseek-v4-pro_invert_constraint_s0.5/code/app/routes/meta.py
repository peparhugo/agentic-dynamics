from flask import Blueprint, jsonify

from app.models import Task

meta_bp = Blueprint("meta", __name__)


@meta_bp.route("/meta", methods=["GET"])
def meta():
    return jsonify({
        "statuses": list(Task.STATUSES),
        "priorities": list(Task.PRIORITIES),
        "default_category": Task.DEFAULT_CATEGORY,
    }), 200
