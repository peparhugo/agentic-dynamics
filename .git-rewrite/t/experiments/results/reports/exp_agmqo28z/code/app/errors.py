from flask import jsonify


class APIError(Exception):
    status_code = 500
    message = "Internal server error"

    def __init__(self, message=None, status_code=None, payload=None):
        super().__init__()
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload or {}

    def to_dict(self):
        d = {"error": self.__class__.__name__, "message": self.message}
        d.update(self.payload)
        return d


class BadRequestError(APIError):
    status_code = 400
    message = "Bad request"


class ValidationError(BadRequestError):
    status_code = 422
    message = "Validation error"


class AuthenticationError(APIError):
    status_code = 401
    message = "Authentication required"


class ForbiddenError(APIError):
    status_code = 403
    message = "Forbidden"


class NotFoundError(APIError):
    status_code = 404
    message = "Resource not found"


class ConflictError(APIError):
    status_code = 409
    message = "Resource conflict"


class RateLimitError(APIError):
    status_code = 429
    message = "Too many requests"


def register_error_handlers(app):

    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(400)
    def handle_bad_request(error):
        return jsonify({"error": "BadRequest", "message": str(error.description)}), 400

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": "NotFound", "message": "The requested URL was not found"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return jsonify({"error": "MethodNotAllowed", "message": "Method not allowed"}), 405

    @app.errorhandler(500)
    def handle_internal_error(error):
        return jsonify({"error": "InternalError", "message": "Internal server error"}), 500
