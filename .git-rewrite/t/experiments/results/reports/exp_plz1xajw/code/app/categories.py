from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.models import Category

categories_bp = Blueprint('categories', __name__)


@categories_bp.route('', methods=['GET'])
@jwt_required()
def get_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify({
        'categories': [c.to_dict() for c in categories],
    }), 200


@categories_bp.route('', methods=['POST'])
@jwt_required()
def create_category():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    name = data.get('name')
    if not name:
        return jsonify({'error': 'Category name is required'}), 400

    if Category.query.filter_by(name=name).first():
        return jsonify({'error': 'Category with this name already exists'}), 409

    category = Category(
        name=name,
        description=data.get('description', ''),
    )

    db.session.add(category)
    db.session.commit()

    return jsonify({
        'message': 'Category created successfully',
        'category': category.to_dict(),
    }), 201


@categories_bp.route('/<int:category_id>', methods=['GET'])
@jwt_required()
def get_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'error': 'Category not found'}), 404

    return jsonify({'category': category.to_dict()}), 200


@categories_bp.route('/<int:category_id>', methods=['PUT'])
@jwt_required()
def update_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'error': 'Category not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'name' in data:
        if not data['name']:
            return jsonify({'error': 'Category name cannot be empty'}), 400
        existing = Category.query.filter_by(name=data['name']).first()
        if existing and existing.id != category_id:
            return jsonify({'error': 'Category with this name already exists'}), 409
        category.name = data['name']

    if 'description' in data:
        category.description = data['description']

    db.session.commit()

    return jsonify({
        'message': 'Category updated successfully',
        'category': category.to_dict(),
    }), 200


@categories_bp.route('/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'error': 'Category not found'}), 404

    from app.models import Task
    if Task.query.filter_by(category_id=category_id).first():
        return jsonify({'error': 'Cannot delete category that has tasks assigned to it'}), 409

    db.session.delete(category)
    db.session.commit()

    return jsonify({'message': 'Category deleted successfully'}), 200
