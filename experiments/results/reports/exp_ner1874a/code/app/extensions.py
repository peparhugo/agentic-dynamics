from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema

# Marshmallow (no global state needed beyond init)
class _MA:
    def init_app(self, app):
        # Placeholder to mirror a typical extension pattern; marshmallow 3 doesn't need init
        pass


ma = _MA()

jwt = JWTManager()

limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
