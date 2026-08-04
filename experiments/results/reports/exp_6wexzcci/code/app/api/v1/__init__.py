from flask import Blueprint

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

from . import auth_routes, items_routes  # noqa: E402,F401
