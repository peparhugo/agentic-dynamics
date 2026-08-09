from flask import request, jsonify, current_app


def get_json_or_400():
    if not request.is_json:
        return None, (jsonify({"error": "bad_request", "message": "Expected application/json"}), 400)
    data = request.get_json(silent=True)
    if data is None:
        return None, (jsonify({"error": "bad_request", "message": "Invalid JSON"}), 400)
    return data, None


def validate_item_payload(data: dict):
    # Minimal explicit validation without extra deps
    if "name" not in data or not isinstance(data["name"], str) or not data["name"].strip():
        return jsonify({"error": "bad_request", "message": "Field 'name' must be a non-empty string"}), 400
    if "quantity" not in data or not isinstance(data["quantity"], int) or data["quantity"] < 0:
        return jsonify({"error": "bad_request", "message": "Field 'quantity' must be a non-negative integer"}), 400
    # Optional fields
    description = data.get("description")
    if description is not None and not isinstance(description, str):
        return jsonify({"error": "bad_request", "message": "Field 'description' must be a string if provided"}), 400
    max_name = 100
    if len(data["name"]) > max_name:
        return jsonify({"error": "bad_request", "message": f"Field 'name' too long (max {max_name})"}), 400
    return None


def parse_pagination_args():
    try:
        limit = int(request.args.get("limit", current_app.config.get("PAGINATION_DEFAULT_LIMIT", 10)))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return None, (jsonify({"error": "bad_request", "message": "Invalid pagination parameters"}), 400)
    max_limit = int(current_app.config.get("PAGINATION_MAX_LIMIT", 100))
    if limit < 1 or limit > max_limit or offset < 0:
        return None, (jsonify({"error": "bad_request", "message": "Invalid pagination range"}), 400)
    return {"limit": limit, "offset": offset}, None
