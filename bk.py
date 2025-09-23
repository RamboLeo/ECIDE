from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
from functools import wraps
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///python_ide.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'user_projects'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

db = SQLAlchemy(app)


# 数据库模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    user = db.relationship('User', backref=db.backref('projects', lazy=True))


class CodeFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # python, image, text, etc.
    file_size = db.Column(db.Integer, default=0)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    project = db.relationship('Project', backref=db.backref('files', lazy=True))
    user = db.relationship('User', backref=db.backref('files', lazy=True))


# 文件上传处理
class FileUpload:
    @staticmethod
    def get_file_type(filename):
        if filename.endswith('.py'):
            return 'python'
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            return 'image'
        elif filename.lower().endswith(('.txt', '.md', '.json', '.xml', '.html', '.css', '.js')):
            return 'text'
        else:
            return 'other'

    @staticmethod
    def save_file(content, filename, user_id, project_name):
        # 确保用户目录存在
        user_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'user_{user_id}')
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)

        # 确保项目目录存在
        project_dir = os.path.join(user_dir, project_name)
        if not os.path.exists(project_dir):
            os.makedirs(project_dir)

        # 保存文件
        file_path = os.path.join(project_dir, filename)
        with open(file_path, 'wb') as f:
            if isinstance(content, str):
                content = content.encode('utf-8')
            f.write(content)

        return file_path


# 创建数据库表
with app.app_context():
    db.create_all()
    # 创建默认管理员账号
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin_user)
        db.session.commit()


# 装饰器：需要token验证
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'message': 'Token缺失'}), 401

        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user or not current_user.is_active:
                return jsonify({'success': False, 'message': '用户不存在或已被禁用'}), 401
        except:
            return jsonify({'success': False, 'message': 'Token无效'}), 401

        return f(current_user, *args, **kwargs)

    return decorated


# 装饰器：需要管理员权限
def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': '需要管理员权限'}), 403
        return f(current_user, *args, **kwargs)

    return decorated


# API路由 - 用户认证
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'})

    user = User(
        username=username,
        password_hash=generate_password_hash(password)
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({'success': True, 'message': '注册成功'})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username, is_active=True).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'success': False, 'message': '用户名或密码错误'})

    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'is_admin': user.is_admin
        }
    })


# API路由 - 代码提交和管理
@app.route('/api/submit_code', methods=['POST'])
@token_required
def submit_code(current_user):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '无效的请求数据'})

        project_name = data.get('project_name')
        file_path = data.get('file_path')
        code_content = data.get('code_content')

        if not all([project_name, file_path, code_content]):
            return jsonify({'success': False, 'message': '参数不完整'})

        # 查找或创建项目
        project = Project.query.filter_by(name=project_name, user_id=current_user.id).first()
        if not project:
            project = Project(name=project_name, user_id=current_user.id)
            db.session.add(project)
            db.session.commit()

        # 确定文件类型
        file_type = FileUpload.get_file_type(file_path)
        file_size = len(code_content.encode('utf-8'))

        # 查找或更新文件
        code_file = CodeFile.query.filter_by(filename=file_path, project_id=project.id).first()
        if code_file:
            code_file.content = code_content
            code_file.file_type = file_type
            code_file.file_size = file_size
            code_file.updated_at = datetime.datetime.utcnow()
        else:
            code_file = CodeFile(
                filename=file_path,
                content=code_content,
                file_type=file_type,
                file_size=file_size,
                project_id=project.id,
                user_id=current_user.id
            )
            db.session.add(code_file)

        db.session.commit()

        return jsonify({'success': True, 'message': '文件提交成功', 'file_id': code_file.id})

    except Exception as e:
        return jsonify({'success': False, 'message': f'提交失败: {str(e)}'})


@app.route('/api/projects', methods=['GET'])
@token_required
def get_projects(current_user):
    projects = Project.query.filter_by(user_id=current_user.id).all()
    result = []
    for project in projects:
        result.append({
            'id': project.id,
            'name': project.name,
            'created_at': project.created_at.isoformat(),
            'file_count': len(project.files)
        })
    return jsonify({'success': True, 'projects': result})


@app.route('/api/project/<int:project_id>/files', methods=['GET'])
@token_required
def get_project_files(current_user, project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权访问此项目'}), 403

    files = CodeFile.query.filter_by(project_id=project_id).all()
    result = []
    for file in files:
        result.append({
            'id': file.id,
            'filename': file.filename,
            'file_type': file.file_type,
            'file_size': file.file_size,
            'created_at': file.created_at.isoformat(),
            'updated_at': file.updated_at.isoformat()
        })
    return jsonify({'success': True, 'files': result})


@app.route('/api/file/<int:file_id>', methods=['GET'])
@token_required
def get_file_content(current_user, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    if code_file.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权访问此文件'}), 403

    return jsonify({
        'success': True,
        'file': {
            'id': code_file.id,
            'filename': code_file.filename,
            'content': code_file.content,
            'file_type': code_file.file_type,
            'file_size': code_file.file_size,
            'created_at': code_file.created_at.isoformat(),
            'updated_at': code_file.updated_at.isoformat(),
            'user_id': code_file.user_id,
            'username': code_file.user.username,
            'project_id': code_file.project_id,
            'project_name': code_file.project.name
        }
    })


@app.route('/api/file/<int:file_id>', methods=['PUT'])
@token_required
def update_file_content(current_user, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    if code_file.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权修改此文件'}), 403

    data = request.get_json()
    new_content = data.get('content')

    if new_content is None:
        return jsonify({'success': False, 'message': '内容不能为空'})

    code_file.content = new_content
    code_file.file_size = len(new_content.encode('utf-8'))
    code_file.updated_at = datetime.datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'message': '文件更新成功'})


@app.route('/api/file/<int:file_id>', methods=['DELETE'])
@token_required
def delete_file(current_user, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    if code_file.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权删除此文件'}), 403

    db.session.delete(code_file)
    db.session.commit()

    return jsonify({'success': True, 'message': '文件删除成功'})


# 管理员接口 - 用户管理
@app.route('/api/admin/users', methods=['GET'])
@token_required
@admin_required
def admin_get_users(current_user):
    users = User.query.all()
    result = []
    for user in users:
        result.append({
            'id': user.id,
            'username': user.username,
            'is_admin': user.is_admin,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat(),
            'project_count': len(user.projects),
            'file_count': len(user.files)
        })
    return jsonify({'success': True, 'users': result})


@app.route('/api/admin/user', methods=['POST'])
@token_required
@admin_required
def admin_create_user(current_user):
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    is_admin = data.get('is_admin', False)

    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'})

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        is_admin=is_admin
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({'success': True, 'message': '用户创建成功'})


@app.route('/api/admin/user/<int:user_id>', methods=['PUT'])
@token_required
@admin_required
def admin_update_user(current_user, user_id):
    if current_user.id == user_id:
        return jsonify({'success': False, 'message': '不能修改自己的账户'}), 400

    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if 'username' in data:
        new_username = data['username']
        if new_username != user.username and User.query.filter_by(username=new_username).first():
            return jsonify({'success': False, 'message': '用户名已存在'})
        user.username = new_username

    if 'password' in data and data['password']:
        user.password_hash = generate_password_hash(data['password'])

    if 'is_admin' in data:
        user.is_admin = data['is_admin']

    if 'is_active' in data:
        user.is_active = data['is_active']

    db.session.commit()

    return jsonify({'success': True, 'message': '用户更新成功'})


@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@token_required
@admin_required
def admin_delete_user(current_user, user_id):
    if current_user.id == user_id:
        return jsonify({'success': False, 'message': '不能删除自己的账户'}), 400

    user = User.query.get_or_404(user_id)

    # 删除用户的所有文件和项目
    CodeFile.query.filter_by(user_id=user_id).delete()
    Project.query.filter_by(user_id=user_id).delete()

    db.session.delete(user)
    db.session.commit()

    return jsonify({'success': True, 'message': '用户删除成功'})


# 管理员接口 - 文件管理
@app.route('/api/admin/files', methods=['GET'])
@token_required
@admin_required
def admin_get_all_files(current_user):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    file_type = request.args.get('type', '')
    user_id = request.args.get('user_id', type=int)

    query = CodeFile.query

    if file_type:
        query = query.filter_by(file_type=file_type)

    if user_id:
        query = query.filter_by(user_id=user_id)

    files = query.order_by(CodeFile.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)

    result = []
    for file in files.items:
        result.append({
            'id': file.id,
            'filename': file.filename,
            'file_type': file.file_type,
            'file_size': file.file_size,
            'user_id': file.user_id,
            'username': file.user.username,
            'project_id': file.project_id,
            'project_name': file.project.name,
            'created_at': file.created_at.isoformat(),
            'updated_at': file.updated_at.isoformat(),
            'content_preview': file.content[:100] + '...' if len(file.content) > 100 else file.content
        })

    return jsonify({
        'success': True,
        'files': result,
        'total': files.total,
        'pages': files.pages,
        'current_page': page
    })


@app.route('/api/admin/file/<int:file_id>', methods=['GET'])
@token_required
@admin_required
def admin_get_file(current_user, file_id):
    code_file = CodeFile.query.get_or_404(file_id)

    return jsonify({
        'success': True,
        'file': {
            'id': code_file.id,
            'filename': code_file.filename,
            'content': code_file.content,
            'file_type': code_file.file_type,
            'file_size': code_file.file_size,
            'user_id': code_file.user_id,
            'username': code_file.user.username,
            'project_id': code_file.project_id,
            'project_name': code_file.project.name,
            'created_at': code_file.created_at.isoformat(),
            'updated_at': code_file.updated_at.isoformat()
        }
    })


@app.route('/api/admin/file/<int:file_id>', methods=['PUT'])
@token_required
@admin_required
def admin_update_file(current_user, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    data = request.get_json()

    if 'content' in data:
        code_file.content = data['content']
        code_file.file_size = len(data['content'].encode('utf-8'))

    if 'filename' in data:
        code_file.filename = data['filename']
        code_file.file_type = FileUpload.get_file_type(data['filename'])

    code_file.updated_at = datetime.datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'message': '文件更新成功'})


@app.route('/api/admin/file/<int:file_id>', methods=['DELETE'])
@token_required
@admin_required
def admin_delete_file(current_user, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    db.session.delete(code_file)
    db.session.commit()

    return jsonify({'success': True, 'message': '文件删除成功'})


# 文件下载接口
@app.route('/api/download/file/<int:file_id>', methods=['GET'])
@token_required
def download_file(current_user, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    if code_file.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权下载此文件'}), 403

    # 创建临时文件
    temp_filename = f"temp_{uuid.uuid4().hex}_{code_file.filename}"
    temp_path = os.path.join('/tmp', temp_filename)

    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(code_file.content)

        return send_file(temp_path, as_attachment=True, download_name=code_file.filename)

    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# 网页界面
@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')


@app.route('/')
def index():
    return render_template('index.html')


# 静态文件服务
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


# 创建模板目录和文件
if not os.path.exists('templates'):
    os.makedirs('templates')

if not os.path.exists('static'):
    os.makedirs('static')

# 创建CSS文件
with open('static/style.css', 'w', encoding='utf-8') as f:
    f.write('''
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    padding: 20px;
    background-color: #f5f5f5;
    color: #333;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 20px;
    border-bottom: 2px solid #eee;
}

h1, h2, h3 {
    color: #2c3e50;
    margin-top: 0;
}

.section {
    margin-bottom: 30px;
    padding: 20px;
    background: #fafafa;
    border-radius: 6px;
    border: 1px solid #ddd;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
    background: white;
}

th, td {
    padding: 12px;
    border: 1px solid #ddd;
    text-align: left;
}

th {
    background-color: #3498db;
    color: white;
    font-weight: 600;
}

tr:nth-child(even) {
    background-color: #f9f9f9;
}

tr:hover {
    background-color: #f1f1f1;
}

.btn {
    padding: 8px 16px;
    margin: 2px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    transition: background-color 0.2s;
}

.btn-primary {
    background-color: #3498db;
    color: white;
}

.btn-primary:hover {
    background-color: #2980b9;
}

.btn-success {
    background-color: #27ae60;
    color: white;
}

.btn-success:hover {
    background-color: #229954;
}

.btn-danger {
    background-color: #e74c3c;
    color: white;
}

.btn-danger:hover {
    background-color: #c0392b;
}

.btn-warning {
    background-color: #f39c12;
    color: white;
}

.btn-warning:hover {
    background-color: #e67e22;
}

.form-group {
    margin-bottom: 15px;
}

.form-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: 600;
}

.form-group input,
.form-group select,
.form-group textarea {
    width: 100%;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
}

.form-group textarea {
    min-height: 100px;
    resize: vertical;
}

.checkbox-group {
    display: flex;
    align-items: center;
    gap: 10px;
}

.checkbox-group input {
    width: auto;
}

.modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.5);
}

.modal-content {
    background-color: white;
    margin: 5% auto;
    padding: 20px;
    border-radius: 8px;
    width: 80%;
    max-width: 600px;
    max-height: 80vh;
    overflow-y: auto;
}

.close {
    float: right;
    font-size: 24px;
    font-weight: bold;
    cursor: pointer;
}

.tabs {
    display: flex;
    border-bottom: 2px solid #3498db;
    margin-bottom: 20px;
}

.tab {
    padding: 10px 20px;
    cursor: pointer;
    border: 1px solid #ddd;
    border-bottom: none;
    background: #f8f9fa;
    margin-right: 5px;
    border-radius: 4px 4px 0 0;
}

.tab.active {
    background: #3498db;
    color: white;
    border-color: #3498db;
}

.tab-content {
    display: none;
}

.tab-content.active {
    display: block;
}

.code-view {
    background: #2d2d2d;
    color: #f8f8f2;
    padding: 15px;
    border-radius: 4px;
    font-family: 'Consolas', 'Monaco', monospace;
    overflow-x: auto;
    max-height: 400px;
    overflow-y: auto;
}

.pagination {
    display: flex;
    justify-content: center;
    margin: 20px 0;
    gap: 5px;
}

.pagination button {
    padding: 8px 12px;
    border: 1px solid #ddd;
    background: white;
    cursor: pointer;
    border-radius: 4px;
}

.pagination button.active {
    background: #3498db;
    color: white;
    border-color: #3498db;
}

.filter-bar {
    display: flex;
    gap: 15px;
    margin-bottom: 20px;
    align-items: center;
    flex-wrap: wrap;
}

.filter-bar select,
.filter-bar input {
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
}

.file-content {
    white-space: pre-wrap;
    word-break: break-all;
}

.alert {
    padding: 15px;
    margin: 10px 0;
    border-radius: 4px;
    border: 1px solid transparent;
}

.alert-success {
    color: #155724;
    background-color: #d4edda;
    border-color: #c3e6cb;
}

.alert-error {
    color: #721c24;
    background-color: #f8d7da;
    border-color: #f5c6cb;
}

.alert-info {
    color: #0c5460;
    background-color: #d1ecf1;
    border-color: #bee5eb;
}
''')

# 创建管理员页面模板
with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>Python IDE - 管理员面板</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Python IDE 管理员面板</h1>
            <div>
                <button class="btn btn-primary" onclick="showModal('userModal')">新建用户</button>
                <button class="btn btn-warning" onclick="logout()">退出登录</button>
            </div>
        </div>

        <div class="tabs">
            <div class="tab active" onclick="switchTab('users')">用户管理</div>
            <div class="tab" onclick="switchTab('files')">文件管理</div>
        </div>

        <div id="alertArea"></div>

        <!-- 用户管理标签 -->
        <div id="usersTab" class="tab-content active">
            <div class="section">
                <h2>用户列表</h2>
                <div id="users-list"></div>
            </div>
        </div>

        <!-- 文件管理标签 -->
        <div id="filesTab" class="tab-content">
            <div class="section">
                <h2>文件管理</h2>
                <div class="filter-bar">
                    <select id="fileTypeFilter" onchange="loadFiles()">
                        <option value="">所有类型</option>
                        <option value="python">Python文件</option>
                        <option value="image">图片文件</option>
                        <option value="text">文本文件</option>
                        <option value="other">其他文件</option>
                    </select>
                    <select id="userFilter" onchange="loadFiles()">
                        <option value="">所有用户</option>
                    </select>
                    <input type="text" id="searchFilter" placeholder="搜索文件名..." oninput="loadFiles()">
                </div>
                <div id="files-list"></div>
                <div class="pagination" id="filesPagination"></div>
            </div>
        </div>

        <!-- 新建用户模态框 -->
        <div id="userModal" class="modal">
            <div class="modal-content">
                <span class="close" onclick="closeModal('userModal')">&times;</span>
                <h2>新建用户</h2>
                <form id="userForm" onsubmit="createUser(event)">
                    <div class="form-group">
                        <label>用户名:</label>
                        <input type="text" id="username" required>
                    </div>
                    <div class="form-group">
                        <label>密码:</label>
                        <input type="password" id="password" required>
                    </div>
                    <div class="form-group checkbox-group">
                        <input type="checkbox" id="isAdmin">
                        <label for="isAdmin">管理员权限</label>
                    </div>
                    <button type="submit" class="btn btn-success">创建用户</button>
                </form>
            </div>
        </div>

        <!-- 编辑用户模态框 -->
        <div id="editUserModal" class="modal">
            <div class="modal-content">
                <span class="close" onclick="closeModal('editUserModal')">&times;</span>
                <h2>编辑用户</h2>
                <form id="editUserForm" onsubmit="updateUser(event)">
                    <input type="hidden" id="editUserId">
                    <div class="form-group">
                        <label>用户名:</label>
                        <input type="text" id="editUsername" required>
                    </div>
                    <div class="form-group">
                        <label>新密码 (留空不修改):</label>
                        <input type="password" id="editPassword">
                    </div>
                    <div class="form-group checkbox-group">
                        <input type="checkbox" id="editIsAdmin">
                        <label for="editIsAdmin">管理员权限</label>
                    </div>
                    <div class="form-group checkbox-group">
                        <input type="checkbox" id="editIsActive">
                        <label for="editIsActive">账户激活</label>
                    </div>
                    <button type="submit" class="btn btn-success">更新用户</button>
                </form>
            </div>
        </div>

        <!-- 文件查看模态框 -->
        <div id="fileViewModal" class="modal">
            <div class="modal-content">
                <span class="close" onclick="closeModal('fileViewModal')">&times;</span>
                <h2>文件内容</h2>
                <div class="form-group">
                    <label>文件名:</label>
                    <input type="text" id="viewFilename" readonly>
                </div>
                <div class="form-group">
                    <label>用户:</label>
                    <input type="text" id="viewUsername" readonly>
                </div>
                <div class="form-group">
                    <label>项目:</label>
                    <input type="text" id="viewProject" readonly>
                </div>
                <div class="form-group">
                    <label>文件内容:</label>
                    <div class="code-view" id="fileContentView"></div>
                </div>
                <div>
                    <button class="btn btn-primary" onclick="downloadFile(currentViewFileId)">下载文件</button>
                    <button class="btn btn-warning" onclick="editFile(currentViewFileId)">编辑文件</button>
                </div>
            </div>
        </div>

        <!-- 文件编辑模态框 -->
        <div id="fileEditModal" class="modal">
            <div class="modal-content">
                <span class="close" onclick="closeModal('fileEditModal')">&times;</span>
                <h2>编辑文件</h2>
                <form id="fileEditForm" onsubmit="saveFileEdit(event)">
                    <input type="hidden" id="editFileId">
                    <div class="form-group">
                        <label>文件名:</label>
                        <input type="text" id="editFilename" required>
                    </div>
                    <div class="form-group">
                        <label>文件内容:</label>
                        <textarea id="editFileContent" required></textarea>
                    </div>
                    <button type="submit" class="btn btn-success">保存修改</button>
                </form>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = '/api';
        let token = localStorage.getItem('token');
        let currentViewFileId = null;
        let currentPage = 1;
        let totalPages = 1;

        if (!token) {
            alert('请先登录');
            window.location.href = '/';
        }

        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            loadUsers();
            loadUsersForFilter();
            loadFiles();
        });

        async function fetchWithAuth(url, options = {}) {
            options.headers = {
                ...options.headers,
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            };
            const response = await fetch(url, options);
            if (response.status === 401) {
                localStorage.removeItem('token');
                alert('登录已过期，请重新登录');
                window.location.href = '/';
                throw new Error('Unauthorized');
            }
            return response;
        }

        function showAlert(message, type = 'info') {
            const alertArea = document.getElementById('alertArea');
            const alert = document.createElement('div');
            alert.className = `alert alert-${type}`;
            alert.textContent = message;
            alertArea.appendChild(alert);

            setTimeout(() => {
                alert.remove();
            }, 5000);
        }

        function switchTab(tabName) {
            // 隐藏所有标签内容
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });

            // 显示选中的标签
            document.getElementById(tabName + 'Tab').classList.add('active');
            document.querySelector(`.tab[onclick="switchTab('${tabName}')"]`).classList.add('active');
        }

        function showModal(modalId) {
            document.getElementById(modalId).style.display = 'block';
        }

        function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }

        async function loadUsers() {
            try {
                const response = await fetchWithAuth(`${API_BASE}/admin/users`);
                const data = await response.json();

                if (data.success) {
                    const usersHtml = `
                        <table>
                            <tr>
                                <th>ID</th>
                                <th>用户名</th>
                                <th>管理员</th>
                                <th>状态</th>
                                <th>注册时间</th>
                                <th>项目数</th>
                                <th>文件数</th>
                                <th>操作</th>
                            </tr>
                        ${data.users.map(user => `
                            <tr>
                                <td>${user.id}</td>
                                <td>${user.username}</td>
                                <td>${user.is_admin ? '是' : '否'}</td>
                                <td>${user.is_active ? '激活' : '禁用'}</td>
                                <td>${new Date(user.created_at).toLocaleString()}</td>
                                <td>${user.project_count}</td>
                                <td>${user.file_count}</td>
                                <td>
                                    <button class="btn btn-primary" onclick="editUser(${user.id}, '${user.username}', ${user.is_admin}, ${user.is_active})">
                                        编辑
                                    </button>
                                    ${user.id !== 1 ? `
                                        <button class="btn btn-danger" onclick="deleteUser(${user.id})">
                                            删除
                                        </button>
                                    ` : ''}
                                </td>
                            </tr>
                        `).join('')}
                        </table>
                    `;
                    document.getElementById('users-list').innerHTML = usersHtml;
                }
            } catch (error) {
                console.error('加载用户失败:', error);
                showAlert('加载用户失败', 'error');
            }
        }

        async function loadUsersForFilter() {
            try {
                const response = await fetchWithAuth(`${API_BASE}/admin/users`);
                const data = await response.json();

                if (data.success) {
                    const userFilter = document.getElementById('userFilter');
                    userFilter.innerHTML = '<option value="">所有用户</option>';
                    data.users.forEach(user => {
                        const option = document.createElement('option');
                        option.value = user.id;
                        option.textContent = user.username;
                        userFilter.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('加载用户过滤器失败:', error);
            }
        }

        async function loadFiles(page = 1) {
            try {
                const fileType = document.getElementById('fileTypeFilter').value;
                const userId = document.getElementById('userFilter').value;
                const search = document.getElementById('searchFilter').value;

                let url = `${API_BASE}/admin/files?page=${page}&per_page=20`;
                if (fileType) url += `&type=${fileType}`;
                if (userId) url += `&user_id=${userId}`;
                if (search) url += `&search=${encodeURIComponent(search)}`;

                const response = await fetchWithAuth(url);
                const data = await response.json();

                if (data.success) {
                    currentPage = data.current_page;
                    totalPages = data.pages;

                    const filesHtml = `
                        <table>
                            <tr>
                                <th>ID</th>
                                <th>文件名</th>
                                <th>类型</th>
                                <th>大小</th>
                                <th>用户</th>
                                <th>项目</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        ${data.files.map(file => `
                            <tr>
                                <td>${file.id}</td>
                                <td>${file.filename}</td>
                                <td>${file.file_type}</td>
                                <td>${formatFileSize(file.file_size)}</td>
                                <td>${file.username} (ID: ${file.user_id})</td>
                                <td>${file.project_name}</td>
                                <td>${new Date(file.created_at).toLocaleString()}</td>
                                <td>
                                    <button class="btn btn-primary" onclick="viewFile(${file.id})">
                                        查看
                                    </button>
                                    <button class="btn btn-warning" onclick="editFile(${file.id})">
                                        编辑
                                    </button>
                                    <button class="btn btn-danger" onclick="deleteFile(${file.id})">
                                        删除
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                        </table>
                    `;
                    document.getElementById('files-list').innerHTML = filesHtml;

                    // 更新分页
                    updatePagination();
                }
            } catch (error) {
                console.error('加载文件失败:', error);
                showAlert('加载文件失败', 'error');
            }
        }

        function updatePagination() {
            const pagination = document.getElementById('filesPagination');
            let html = '';

            if (currentPage > 1) {
                html += `<button onclick="loadFiles(${currentPage - 1})">上一页</button>`;
            }

            for (let i = 1; i <= totalPages; i++) {
                if (i === currentPage) {
                    html += `<button class="active">${i}</button>`;
                } else {
                    html += `<button onclick="loadFiles(${i})">${i}</button>`;
                }
            }

            if (currentPage < totalPages) {
                html += `<button onclick="loadFiles(${currentPage + 1})">下一页</button>`;
            }

            pagination.innerHTML = html;
        }

        function formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        async function createUser(event) {
            event.preventDefault();

            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const isAdmin = document.getElementById('isAdmin').checked;

            try {
                const response = await fetchWithAuth(`${API_BASE}/admin/user`, {
                    method: 'POST',
                    body: JSON.stringify({ username, password, is_admin: isAdmin })
                });

                const data = await response.json();

                if (data.success) {
                    showAlert('用户创建成功', 'success');
                    closeModal('userModal');
                    document.getElementById('userForm').reset();
                    loadUsers();
                    loadUsersForFilter();
                } else {
                    showAlert(data.message, 'error');
                }
            } catch (error) {
                console.error('创建用户失败:', error);
                showAlert('创建用户失败', 'error');
            }
        }

        async function editUser(userId, username, isAdmin, isActive) {
            document.getElementById('editUserId').value = userId;
            document.getElementById('editUsername').value = username;
            document.getElementById('editIsAdmin').checked = isAdmin;
            document.getElementById('editIsActive').checked = isActive;
            showModal('editUserModal');
        }

        async function updateUser(event) {
            event.preventDefault();

            const userId = document.getElementById('editUserId').value;
            const username = document.getElementById('editUsername').value;
            const password = document.getElementById('editPassword').value;
            const isAdmin = document.getElementById('editIsAdmin').checked;
            const isActive = document.getElementById('editIsActive').checked;

            try {
                const response = await fetchWithAuth(`${API_BASE}/admin/user/${userId}`, {
                    method: 'PUT',
                    body: JSON.stringify({ 
                        username, 
                        password: password || undefined,
                        is_admin: isAdmin,
                        is_active: isActive
                    })
                });

                const data = await response.json();

                if (data.success) {
                    showAlert('用户更新成功', 'success');
                    closeModal('editUserModal');
                    document.getElementById('editUserForm').reset();
                    loadUsers();
                    loadUsersForFilter();
                } else {
                    showAlert(data.message, 'error');
                }
            } catch (error) {
                console.error('更新用户失败:', error);
                showAlert('更新用户失败', 'error');
            }
        }

        async function deleteUser(userId) {
            if (confirm('确定要删除这个用户吗？这将删除该用户的所有项目和文件！')) {
                try {
                    const response = await fetchWithAuth(`${API_BASE}/admin/user/${userId}`, {
                        method: 'DELETE'
                    });

                    const data = await response.json();

                    if (data.success) {
                        showAlert('用户删除成功', 'success');
                        loadUsers();
                        loadUsersForFilter();
                    } else {
                        showAlert(data.message, 'error');
                    }
                } catch (error) {
                    console.error('删除用户失败:', error);
                    showAlert('删除用户失败', 'error');
                }
            }
        }

        async function viewFile(fileId) {
            try {
                const response = await fetchWithAuth(`${API_BASE}/admin/file/${fileId}`);
                const data = await response.json();

                if (data.success) {
                    currentViewFileId = fileId;
                    document.getElementById('viewFilename').value = data.file.filename;
                    document.getElementById('viewUsername').value = `${data.file.username} (ID: ${data.file.user_id})`;
                    document.getElementById('viewProject').value = data.file.project_name;

                    // 根据文件类型格式化显示
                    const contentElement = document.getElementById('fileContentView');
                    if (data.file.file_type === 'python' || data.file.file_type === 'text') {
                        contentElement.textContent = data.file.content;
                        contentElement.className = 'code-view';
                    } else if (data.file.file_type === 'image') {
                        contentElement.innerHTML = `<img src="data:image/png;base64,${btoa(data.file.content)}" 
                            style="max-width: 100%; max-height: 300px;" alt="图片预览">`;
                        contentElement.className = '';
                    } else {
                        contentElement.textContent = data.file.content;
                        contentElement.className = 'file-content';
                    }

                    showModal('fileViewModal');
                }
            } catch (error) {
                console.error('查看文件失败:', error);
                showAlert('查看文件失败', 'error');
            }
        }

        async function editFile(fileId) {
            try {
                const response = await fetchWithAuth(`${API_BASE}/admin/file/${fileId}`);
                const data = await response.json();

                if (data.success) {
                    document.getElementById('editFileId').value = fileId;
                    document.getElementById('editFilename').value = data.file.filename;
                    document.getElementById('editFileContent').value = data.file.content;
                    showModal('fileEditModal');
                }
            } catch (error) {
                console.error('加载文件编辑失败:', error);
                showAlert('加载文件编辑失败', 'error');
            }
        }

        async function saveFileEdit(event) {
            event.preventDefault();

            const fileId = document.getElementById('editFileId').value;
            const filename = document.getElementById('editFilename').value;
            const content = document.getElementById('editFileContent').value;

            try {
                const response = await fetchWithAuth(`${API_BASE}/admin/file/${fileId}`, {
                    method: 'PUT',
                    body: JSON.stringify({ filename, content })
                });

                const data = await response.json();

                if (data.success) {
                    showAlert('文件更新成功', 'success');
                    closeModal('fileEditModal');
                    loadFiles(currentPage);
                } else {
                    showAlert(data.message, 'error');
                }
            } catch (error) {
                console.error('保存文件失败:', error);
                showAlert('保存文件失败', 'error');
            }
        }

        async function deleteFile(fileId) {
            if (confirm('确定要删除这个文件吗？')) {
                try {
                    const response = await fetchWithAuth(`${API_BASE}/admin/file/${fileId}`, {
                        method: 'DELETE'
                    });

                    const data = await response.json();

                    if (data.success) {
                        showAlert('文件删除成功', 'success');
                        loadFiles(currentPage);
                    } else {
                        showAlert(data.message, 'error');
                    }
                } catch (error) {
                    console.error('删除文件失败:', error);
                    showAlert('删除文件失败', 'error');
                }
            }
        }

        async function downloadFile(fileId) {
            try {
                window.open(`${API_BASE}/download/file/${fileId}?token=${token}`, '_blank');
            } catch (error) {
                console.error('下载文件失败:', error);
                showAlert('下载文件失败', 'error');
            }
        }

        function logout() {
            localStorage.removeItem('token');
            window.location.href = '/';
        }

        // 点击模态框外部关闭
        window.onclick = function(event) {
            if (event.target.className === 'modal') {
                event.target.style.display = 'none';
            }
        }
    </script>
</body>
</html>''')

# 创建首页模板
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>Python IDE - 后端系统</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <h1>Python IDE 后端系统</h1>
        <p>这是一个用于代码提交和管理的后端系统</p>

        <div class="section">
            <h3>管理员登录</h3>
            <form onsubmit="login(event)">
                <div class="form-group">
                    <label>用户名:</label>
                    <input type="text" id="username" value="admin" required>
                </div>
                <div class="form-group">
                    <label>密码:</label>
                    <input type="password" id="password" value="admin123" required>
                </div>
                <button type="submit" class="btn btn-primary">登录</button>
            </form>
        </div>

        <p>普通用户请使用 Python IDE 客户端进行登录和操作</p>
        <p>管理员账号: admin / admin123</p>
    </div>

    <script>
        async function login(event) {
            event.preventDefault();

            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });

                const data = await response.json();

                if (data.success) {
                    localStorage.setItem('token', data.token);
                    if (data.user.is_admin) {
                        window.location.href = '/admin';
                    } else {
                        alert('普通用户请使用客户端操作');
                    }
                } else {
                    alert('登录失败: ' + data.message);
                }
            } catch (error) {
                alert('登录失败: ' + error.message);
            }
        }
    </script>
</body>
</html>''')

if __name__ == '__main__':
    # 确保上传目录存在
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    app.run(host='0.0.0.0', port=8080, debug=True)