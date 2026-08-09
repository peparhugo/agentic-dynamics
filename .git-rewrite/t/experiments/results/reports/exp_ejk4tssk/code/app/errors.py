from flask import jsonify
from werkzeug.exceptions import HTTPException

class APIError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err):
        response = jsonify({"error": err.message})
        response.status_code = err.status_code
        return response

    @app.errorhandler(HTTPException)
    def handle_http_exception(err):
        response = jsonify({"error": err.description})
        response.status_code = err.code or 500
        return response

    @app.errorhandler(Exception)
    def handle_uncaught(err):
        # Hide internal details
        response = jsonify({"error": "internal_server_error"})
        response.status_code = 500
        return response
