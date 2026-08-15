from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from models import db, Priority

priorities_bp = Blueprint('priorities', __name__, url_prefix='/api/priorities')

@priorities_bp.route('', methods=['GET'])
@jwt_required()
def get_priorities():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    paginated = Priority.query.order_by(Priority.level).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'priorities': [pri.to_dict() for pri in paginated.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages
        }
    }), 200

@priorities_bp.route('/<int:priority_id>', methods=['GET'])
@jwt_required()
def get_priority(priority_id):
    priority = Priority.query.get(priority_id)

    if not priority:
        return jsonify({'message': 'Priority not found'}), 404

    return jsonify(priority.to_dict()), 200

@priorities_bp.route('', methods=['POST'])
@jwt_required()
def create_priority():
    data = request.get_json()

    if not data or not data.get('name') or 'level' not in data:
        return jsonify({'message': 'Name and level are required'}), 400

    priority = Priority(
        name=data.get('name'),
        level=data.get('level')
    )

    db.session.add(priority)
    db.session.commit()

    return jsonify({'message': 'Priority created successfully', 'priority': priority.to_dict()}), 201

@priorities_bp.route('/<int:priority_id>', methods=['PUT'])
@jwt_required()
def update_priority(priority_id):
    priority = Priority.query.get(priority_id)

    if not priority:
        return jsonify({'message': 'Priority not found'}), 404

    data = request.get_json()

    if 'name' in data:
        priority.name = data['name']
    if 'level' in data:
        priority.level = data['level']

    db.session.commit()

    return jsonify({'message': 'Priority updated successfully', 'priority': priority.to_dict()}), 200

@priorities_bp.route('/<int:priority_id>', methods=['DELETE'])
@jwt_required()
def delete_priority(priority_id):
    priority = Priority.query.get(priority_id)

    if not priority:
        return jsonify({'message': 'Priority not found'}), 404

    db.session.delete(priority)
    db.session.commit()

    return jsonify({'message': 'Priority deleted successfully'}), 200
