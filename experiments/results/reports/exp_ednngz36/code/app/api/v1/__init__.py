from flask import Blueprint

bp = Blueprint("api_v1", __name__)

from . import auth_routes, notes_routes, admin_routes  # noqa: E402,F401
