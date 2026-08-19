from flask import jsonify


class ApiError(Exception):
    def __init__(self, message, status_code=400, errors=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        payload = {"error": err.message}
        if err.errors:
            payload["errors"] = err.errors
        return jsonify(payload), err.status_code

    @app.errorhandler(404)
    def handle_404(err):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def handle_405(err):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(400)
    def handle_400(err):
        return jsonify({"error": "Bad request"}), 400
