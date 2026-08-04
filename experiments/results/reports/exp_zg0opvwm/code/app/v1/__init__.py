from flask import Blueprint

bp = Blueprint("v1", __name__)

from app.v1 import auth_routes, resources  # noqa: E402, F401
