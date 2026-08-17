from flask import jsonify


class ApiError(Exception):
    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload or {}

    def to_dict(self):
        body = dict(self.payload)
        body["error"] = self.message
        return body


class ValidationError(ApiError):
    status_code = 400


class NotFoundError(ApiError):
    status_code = 404


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        response = jsonify(err.to_dict())
        response.status_code = err.status_code
        return response

    @app.errorhandler(404)
    def handle_404(err):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def handle_405(err):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(400)
    def handle_400(err):
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(500)
    def handle_500(err):
        return jsonify({"error": "Internal server error"}), 500
