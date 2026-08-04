from flask import Blueprint

bp = Blueprint("api_v1", __name__)

from app.api.v1 import auth  # noqa: E402, F401
from app.api.v1 import items  # noqa: E402, F401
