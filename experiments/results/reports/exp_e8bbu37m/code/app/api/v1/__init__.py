"""API v1 blueprint. New versions live alongside (e.g. app/api/v2)."""
from flask import Blueprint

API_VERSION = "1"

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


@bp.after_request
def add_version_header(response):
    response.headers["X-API-Version"] = API_VERSION
    return response


from . import auth, items  # noqa: E402,F401  (register routes)
