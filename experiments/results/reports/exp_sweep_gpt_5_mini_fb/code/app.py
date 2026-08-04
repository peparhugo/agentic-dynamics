from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
import datetime, uuid, threading, time
import jwt

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'test-secret'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class RefreshToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(200), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(50), nullable=False)
    resource = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(500), nullable=True)
    ts = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()

rate_lock = threading.Lock()
rate_store = {}

def rate_limited(ip):
    now = time.time()
    window = 60
    limit = 5
    with rate_lock:
        arr = rate_store.get(ip, [])
        arr = [t for t in arr if now - t < window]
        if len(arr) >= limit:
            rate_store[ip] = arr
            return True
        arr.append(now)
        rate_store[ip] = arr
        return False

def create_access_token(user_id, exp_seconds=60):
    payload = {'sub': str(user_id), 'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=exp_seconds)}
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token

def require_auth(f):
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization','')
        if not auth.startswith('Bearer '):
            return jsonify({'error':'missing auth'}),401
        token = auth.split(None,1)[1]
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        except Exception:
            return jsonify({'error':'invalid token'}),401
        g.user_id = data.get('sub')
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error':'bad request'}),400

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error':'not found'}),404

@app.route('/v1/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username','').strip()
    password = data.get('password','')
    if not username or not password or len(password) < 4:
        return jsonify({'error':'invalid input'}),400
    if User.query.filter_by(username=username).first():
        return jsonify({'error':'user exists'}),400
    u = User(username=username, password=password)
    db.session.add(u)
    db.session.commit()
    return jsonify({'id':u.id,'username':u.username}),201

@app.route('/v1/auth/login', methods=['POST'])
def login():
    ip = request.remote_addr or '127.0.0.1'
    if rate_limited(ip):
        return jsonify({'error':'too many attempts'}),429
    data = request.get_json() or {}
    username = data.get('username','')
    password = data.get('password','')
    if not username or not password:
        return jsonify({'error':'invalid input'}),400
    user = User.query.filter_by(username=username).first()
    if not user or user.password != password:
        return jsonify({'error':'invalid credentials'}),401
    access = create_access_token(user.id)
    token = str(uuid.uuid4())
    rt = RefreshToken(user_id=user.id, token=token, expires_at=datetime.datetime.utcnow()+datetime.timedelta(days=7))
    db.session.add(rt)
    db.session.commit()
    return jsonify({'access_token':access, 'refresh_token':token}),200

@app.route('/v1/auth/refresh', methods=['POST'])
def refresh():
    data = request.get_json() or {}
    token = data.get('refresh_token')
    if not token:
        return jsonify({'error':'invalid input'}),400
    rt = RefreshToken.query.filter_by(token=token).first()
    if not rt or rt.expires_at < datetime.datetime.utcnow():
        return jsonify({'error':'invalid refresh'}),401
    access = create_access_token(rt.user_id)
    return jsonify({'access_token':access}),200

@app.route('/v1/users', methods=['GET'])
@require_auth
def list_users():
    try:
        page = int(request.args.get('page',1))
        per = int(request.args.get('per_page',20))
    except Exception:
        return jsonify({'error':'invalid params'}),400
    if per < 1: per = 1
    if per > 100: per = 100
    q = User.query
    total = q.count()
    items = q.offset((page-1)*per).limit(per).all()
    return jsonify({'total':total,'page':page,'per_page':per,'items':[{'id':u.id,'username':u.username} for u in items]}),200

def audit(action, resource, details=None):
    try:
        a = AuditLog(user_id=getattr(g,'user_id',None), action=action, resource=resource, details=details)
        db.session.add(a)
        db.session.commit()
    except Exception:
        db.session.rollback()

@app.route('/v1/users/<int:user_id>', methods=['PUT'])
@require_auth
def update_user(user_id):
    u = User.query.get(user_id)
    if not u:
        return jsonify({'error':'not found'}),404
    data = request.get_json() or {}
    username = data.get('username')
    if username:
        if User.query.filter(User.username==username, User.id!=user_id).first():
            return jsonify({'error':'username taken'}),400
        u.username = username
    db.session.commit()
    audit('update','user:'+str(user_id),str(data))
    return jsonify({'id':u.id,'username':u.username}),200

@app.route('/v1/users/<int:user_id>', methods=['DELETE'])
@require_auth
def delete_user(user_id):
    u = User.query.get(user_id)
    if not u:
        return jsonify({'error':'not found'}),404
    db.session.delete(u)
    db.session.commit()
    audit('delete','user:'+str(user_id))
    return jsonify({}),204

if __name__ == '__main__':
    app.run()
