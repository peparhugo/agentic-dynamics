from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from models import db, Category

categories_bp = Blueprint('categories', __name__, url_prefix='/api/categories')

@categories_bp.route('', methods=['GET'])
@jwt_required()
def get_categories():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    paginated = Category.query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'categories': [cat.to_dict() for cat in paginated.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages
        }
    }), 200

@categories_bp.route('/<int:category_id>', methods=['GET'])
@jwt_required()
def get_category(category_id):
    category = Category.query.get(category_id)

    if not category:
        return jsonify({'message': 'Category not found'}), 404

    return jsonify(category.to_dict()), 200

@categories_bp.route('', methods=['POST'])
@jwt_required()
def create_category():
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({'message': 'Name is required'}), 400

    category = Category(
        name=data.get('name'),
        description=data.get('description')
    )

    db.session.add(category)
    db.session.commit()

    return jsonify({'message': 'Category created successfully', 'category': category.to_dict()}), 201

@categories_bp.route('/<int:category_id>', methods=['PUT'])
@jwt_required()
def update_category(category_id):
    category = Category.query.get(category_id)

    if not category:
        return jsonify({'message': 'Category not found'}), 404

    data = request.get_json()

    if 'name' in data:
        category.name = data['name']
    if 'description' in data:
        category.description = data['description']

    db.session.commit()

    return jsonify({'message': 'Category updated successfully', 'category': category.to_dict()}), 200

@categories_bp.route('/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_category(category_id):
    category = Category.query.get(category_id)

    if not category:
        return jsonify({'message': 'Category not found'}), 404

    db.session.delete(category)
    db.session.commit()

    return jsonify({'message': 'Category deleted successfully'}), 200
