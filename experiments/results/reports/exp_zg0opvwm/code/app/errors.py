from flask import jsonify


class APIError(Exception):
    def __init__(self, message, status_code=400, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = {"error": error.message}
        if error.details:
            response["details"] = error.details
        return jsonify(response), error.status_code

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def handle_internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(413)
    def handle_request_too_large(error):
        return jsonify({"error": "Request too large"}), 413
