from flask_jwt_extended import create_access_token
from models import User, db

def create_user_token(user):
    access_token = create_access_token(identity=str(user.id))
    return access_token

def authenticate_user(username, password):
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return user
    return None

def register_user(username, email, password):
    if User.query.filter_by(username=username).first():
        return None, 'Username already exists'
    if User.query.filter_by(email=email).first():
        return None, 'Email already exists'

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user, None
