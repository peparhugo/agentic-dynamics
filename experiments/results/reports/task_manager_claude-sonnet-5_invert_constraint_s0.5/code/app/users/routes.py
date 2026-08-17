from flask import jsonify, Blueprint
from flask_jwt_extended import jwt_required

from app.models import User
from app.utils import paginate_args, paginated_response

users_bp = Blueprint("users", __name__)


@users_bp.route("", methods=["GET"])
@jwt_required()
def list_users():
    page, per_page = paginate_args()
    query = User.query.order_by(User.username.asc())
    return jsonify(paginated_response(query, page, per_page))
