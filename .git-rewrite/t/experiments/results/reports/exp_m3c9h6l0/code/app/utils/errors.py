from flask import jsonify


class APIError(Exception):
    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload or {}

    def to_dict(self):
        d = dict(self.payload)
        d["error"] = self.message
        d["status_code"] = self.status_code
        return d


class BadRequest(APIError):
    status_code = 400


class Unauthorized(APIError):
    status_code = 401


class Forbidden(APIError):
    status_code = 403


class NotFound(APIError):
    status_code = 404


class Conflict(APIError):
    status_code = 409


class TooManyRequests(APIError):
    status_code = 429


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(422)
    def handle_marshmallow_validation(error):
        messages = getattr(error, "data", {}).get("messages", ["Validation failed"])
        return jsonify({"error": "Validation failed", "details": messages, "status_code": 422}), 422

    @app.errorhandler(429)
    def handle_ratelimit_error(error):
        return jsonify({"error": "Too many requests", "status_code": 429}), 429
