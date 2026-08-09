"""API v1 blueprint.

Versioning strategy: URL-prefix based (/api/v1). A future v2 gets its own
package (app/api/v2) and blueprint, allowing both versions to be served
side by side during migration windows.
"""
from flask import Blueprint

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

from app.api.v1 import auth, items  # noqa: E402,F401  (route registration)
