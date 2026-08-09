from flask import jsonify


def handle_error(error, status_code=500):
    return (
        jsonify(
            {
                "error": {
                    "message": str(error),
                    "code": status_code,
                }
            }
        ),
        status_code,
    )


def register_error_handlers(app):

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": {"message": str(error) or "Bad request", "code": 400}}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": {"message": str(error) or "Unauthorized", "code": 401}}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"error": {"message": str(error) or "Forbidden", "code": 403}}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": {"message": str(error) or "Not found", "code": 404}}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"error": {"message": str(error) or "Method not allowed", "code": 405}}), 405

    @app.errorhandler(429)
    def ratelimit_error(error):
        return jsonify({"error": {"message": "Rate limit exceeded", "code": 429}}), 429

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": {"message": "Internal server error", "code": 500}}), 500
