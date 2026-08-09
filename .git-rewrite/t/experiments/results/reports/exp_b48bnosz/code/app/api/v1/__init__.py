"""API v1 blueprint. Mounted at /api/v1."""
from flask import Blueprint

bp = Blueprint("api_v1", __name__)

from . import auth, items, audit  # noqa: E402,F401  (route registration)
