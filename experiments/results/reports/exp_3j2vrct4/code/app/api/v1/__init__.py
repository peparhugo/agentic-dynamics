from flask import Blueprint

bp = Blueprint("api_v1", __name__)

from . import auth_routes, notes  # noqa: E402,F401  (route registration)
