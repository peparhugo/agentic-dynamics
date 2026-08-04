import os
import logging
from flask import Flask, jsonify, request, g
from .auth import jwt_required, create_token, decode_token
from .rate_limiter import rate_limit_middleware
from .audit import audit_log
from .schemas import validate_item_payload
from datetime import datetime

def create_app():
    app = Flask(__name__)
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
    app.config['JWT_SECRET'] = os.environ.get('JWT_SECRET', 'dev-secret')

    # Simple in-memory store for demo purposes
    app.items = []

    # Logging
    logging.basicConfig(level=logging.INFO)

    # Register middleware
    app.before_request(rate_limit_middleware)
    app.after_request(audit_log)

    # Error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'error': 'bad_request', 'message': getattr(e, 'description', 'Bad request')}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({'error': 'unauthorized', 'message': getattr(e, 'description', 'Unauthorized')}), 401

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'not_found', 'message': getattr(e, 'description', 'Not found')}), 404

    @app.errorhandler(429)
    def too_many(e):
        return jsonify({'error': 'rate_limited', 'message': getattr(e, 'description', 'Too many requests')}), 429

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'error': 'server_error', 'message': 'An internal error occurred'}), 500

    # API routes (versioned)
    @app.route('/api/v1/token', methods=['POST'])
    def token():
        """Issue a token. Accepts JSON with 'sub' (username). In production use real auth."""
        data = request.get_json() or {}
        sub = data.get('sub')
        if not sub:
            return jsonify({'error': 'invalid_input', 'message': 'sub is required'}), 400
        token = create_token(sub, app.config['JWT_SECRET'])
        return jsonify({'access_token': token}), 201

    @app.route('/api/v1/items', methods=['GET'])
    def list_items():
        # pagination
        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = int(request.args.get('per_page', 10))
        except ValueError:
            return jsonify({'error': 'invalid_input', 'message': 'page and per_page must be integers'}), 400
        per_page = min(max(1, per_page), 100)
        start = (page - 1) * per_page
        end = start + per_page
        total = len(app.items)
        items = app.items[start:end]
        return jsonify({'data': items, 'page': page, 'per_page': per_page, 'total': total}), 200

    @app.route('/api/v1/items', methods=['POST'])
    @jwt_required
    def create_item():
        payload = request.get_json() or {}
        errors = validate_item_payload(payload)
        if errors:
            return jsonify({'error': 'invalid_input', 'message': errors}), 400
        item = {
            'id': len(app.items) + 1,
            'name': payload['name'],
            'description': payload.get('description', ''),
            'created_by': g.user,
            'created_at': datetime.utcnow().isoformat() + 'Z'
        }
        app.items.append(item)
        return jsonify(item), 201

    @app.route('/api/v1/items/<int:item_id>', methods=['GET'])
    def get_item(item_id):
        for it in app.items:
            if it['id'] == item_id:
                return jsonify(it), 200
        return jsonify({'error': 'not_found', 'message': 'item not found'}), 404

    return app
