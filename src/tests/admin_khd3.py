from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ide.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# 用户模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    submission_count = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# 创建数据库表
with app.app_context():
    db.create_all()


# JWT认证装饰器
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
        except:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)

    return decorated


# 管理员权限装饰器
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])

            if not current_user.is_admin:
                return jsonify({'message': 'Admin privileges required!'}), 403
        except:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)

    return decorated


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空!'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在!'}), 400

    new_user = User(username=username)
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'success': True, 'message': '注册成功!'})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空!'}), 400

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': '用户名或密码错误!'}), 401

    # 更新最后登录时间
    user.last_login = datetime.utcnow()
    db.session.commit()

    # 生成JWT token
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, app.config['SECRET_KEY'])

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'is_admin': user.is_admin,
            'created_at': user.created_at.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'submission_count': user.submission_count
        }
    })


@app.route('/api/users', methods=['GET'])
@admin_required
@token_required
def get_users(current_user):
    users = User.query.all()
    output = []

    for user in users:
        user_data = {
            'id': user.id,
            'username': user.username,
            'is_admin': user.is_admin,
            'active': user.active,
            'created_at': user.created_at.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'submission_count': user.submission_count
        }
        output.append(user_data)

    return jsonify({'success': True, 'users': output})


@app.route('/api/users/create', methods=['POST'])
@admin_required
@token_required
def create_user(current_user):
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    is_admin = data.get('is_admin', False)

    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空!'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在!'}), 400

    new_user = User(username=username, is_admin=is_admin)
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'success': True, 'message': '用户创建成功!'})


@app.route('/api/users/<int:user_id>/edit', methods=['PUT'])
@admin_required
@token_required
def edit_user(current_user, user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在!'}), 404

    data = request.get_json()

    if 'username' in data:
        new_username = data['username']
        if new_username != user.username and User.query.filter_by(username=new_username).first():
            return jsonify({'success': False, 'message': '用户名已存在!'}), 400
        user.username = new_username

    if 'password' in data and data['password']:
        user.set_password(data['password'])

    if 'is_admin' in data:
        user.is_admin = data['is_admin']

    if 'active' in data:
        user.active = data['active']

    db.session.commit()
    return jsonify({'success': True, 'message': '用户信息已更新!'})


@app.route('/api/users/<int:user_id>/delete', methods=['DELETE'])
@admin_required
@token_required
def delete_user(current_user, user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在!'}), 404

    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': '用户已删除!'})


@app.route('/api/users/<int:user_id>/set_admin', methods=['PUT'])
@admin_required
@token_required
def make_admin(current_user, user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在!'}), 404

    user.is_admin = True
    db.session.commit()
    return jsonify({'success': True, 'message': '用户已设为管理员!'})


@app.route('/api/users/<int:user_id>/remove_admin', methods=['PUT'])
@admin_required
@token_required
def remove_admin(current_user, user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在!'}), 404

    user.is_admin = False
    db.session.commit()
    return jsonify({'success': True, 'message': '用户已取消管理员权限!'})


if __name__ == '__main__':
    app.run(debug=True, port=8081)