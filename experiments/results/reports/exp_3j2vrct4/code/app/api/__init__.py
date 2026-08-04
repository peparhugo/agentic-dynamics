"""Versioned API registry.

Each version exposes a `bp` blueprint mounted at /api/<version>.
Adding v2 = create app/api/v2/, list it in VERSIONS, done.
"""
from . import v1

VERSIONS = {"v1": v1.bp}
CURRENT_VERSION = "v1"


def register_versions(app):
    for name, bp in VERSIONS.items():
        app.register_blueprint(bp, url_prefix=f"/api/{name}")
