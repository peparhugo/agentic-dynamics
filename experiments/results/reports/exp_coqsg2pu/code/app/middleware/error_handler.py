from flask import jsonify


def register_error_handlers(app):

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error="Bad request", detail=str(e.description)), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify(error="Unauthorized", detail=str(e.description)), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify(error="Forbidden", detail=str(e.description)), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Not found", detail=str(e.description)), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify(error="Method not allowed", detail=str(e.description)), 405

    @app.errorhandler(429)
    def ratelimit_exceeded(e):
        return jsonify(error="Rate limit exceeded", detail=str(e.description), retry_after=e.retry_after), 429

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify(error="Internal server error", detail="An unexpected error occurred"), 500
