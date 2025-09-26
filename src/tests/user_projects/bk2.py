from flask import Flask, request, jsonify, send_file, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
from functools import wraps
#管理员密码admin admin123
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///python_ide.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'user_projects'

db = SQLAlchemy(app)


# 数据库模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


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
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    project = db.relationship('Project', backref=db.backref('files', lazy=True))
    user = db.relationship('User', backref=db.backref('files', lazy=True))


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


# API路由
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

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'success': False, 'message': '用户名或密码错误'})

    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({
        'success': True,
        'token': token,
        'user': {'id': user.id, 'username': user.username, 'is_admin': user.is_admin}
    })


@app.route('/api/submit_code', methods=['POST'])
@token_required
def submit_code(current_user):
    data = request.get_json()
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

    # 查找或更新文件
    code_file = CodeFile.query.filter_by(filename=file_path, project_id=project.id).first()
    if code_file:
        code_file.content = code_content
        code_file.updated_at = datetime.datetime.utcnow()
    else:
        code_file = CodeFile(
            filename=file_path,
            content=code_content,
            project_id=project.id,
            user_id=current_user.id
        )
        db.session.add(code_file)

    db.session.commit()

    return jsonify({'success': True, 'message': '代码提交成功'})


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
            'created_at': code_file.created_at.isoformat(),
            'updated_at': code_file.updated_at.isoformat()
        }
    })


@app.route('/api/file/<int:file_id>', methods=['DELETE'])
@token_required
def delete_file(current_user, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    if code_file.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权删除此文件'}), 403

    db.session.delete(code_file)
    db.session.commit()

    return jsonify({'success': True, 'message': '文件删除成功'})


# 管理员接口
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
            'created_at': user.created_at.isoformat(),
            'project_count': len(user.projects),
            'file_count': len(user.files)
        })
    return jsonify({'success': True, 'users': result})


@app.route('/api/admin/files', methods=['GET'])
@token_required
@admin_required
def admin_get_all_files(current_user):
    files = CodeFile.query.all()
    result = []
    for file in files:
        result.append({
            'id': file.id,
            'filename': file.filename,
            'user_id': file.user_id,
            'username': file.user.username,
            'project_id': file.project_id,
            'project_name': file.project.name,
            'created_at': file.created_at.isoformat(),
            'updated_at': file.updated_at.isoformat()
        })
    return jsonify({'success': True, 'files': result})


@app.route('/api/admin/file/<int:file_id>', methods=['DELETE'])
@token_required
@admin_required
def admin_delete_file(current_user, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    db.session.delete(code_file)
    db.session.commit()

    return jsonify({'success': True, 'message': '文件删除成功'})


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


# 网页界面
@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')


@app.route('/')
def index():
    return render_template('index.html')


# 创建模板目录和文件
if not os.path.exists('templates'):
    os.makedirs('templates')

# 创建管理员页面模板
with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>Python IDE - 管理员面板</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .section { margin-bottom: 30px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
        th { background-color: #f5f5f5; }
        .btn { padding: 5px 10px; margin: 2px; cursor: pointer; }
        .btn-danger { background-color: #dc3545; color: white; border: none; }
    </style>
</head>
<body>
    <h1>Python IDE 管理员面板</h1>

    <div class="section">
        <h2>用户管理</h2>
        <div id="users-list"></div>
    </div>

    <div class="section">
        <h2>文件管理</h2>
        <div id="files-list"></div>
    </div>

    <script>
        const API_BASE = '/api';
        let token = localStorage.getItem('token');

        if (!token) {
            alert('请先登录');
            window.location.href = '/';
        }

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
            }
            return response;
        }

        async function loadUsers() {
            const response = await fetchWithAuth(`${API_BASE}/admin/users`);
            const data = await response.json();

            if (data.success) {
                const usersHtml = `
                    <table>
                        <tr>
                            <th>ID</th>
                            <th>用户名</th>
                            <th>管理员</th>
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
                                <td>${new Date(user.created_at).toLocaleString()}</td>
                                <td>${user.project_count}</td>
                                <td>${user.file_count}</td>
                                <td>
                                    ${!user.is_admin ? `
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
        }

        async function loadFiles() {
            const response = await fetchWithAuth(`${API_BASE}/admin/files`);
            const data = await response.json();

            if (data.success) {
                const filesHtml = `
                    <table>
                        <tr>
                            <th>ID</th>
                            <th>文件名</th>
                            <th>用户</th>
                            <th>项目</th>
                            <th>创建时间</th>
                            <th>更新时间</th>
                            <th>操作</th>
                        </tr>
                        ${data.files.map(file => `
                            <tr>
                                <td>${file.id}</td>
                                <td>${file.filename}</td>
                                <td>${file.username} (ID: ${file.user_id})</td>
                                <td>${file.project_name}</td>
                                <td>${new Date(file.created_at).toLocaleString()}</td>
                                <td>${new Date(file.updated_at).toLocaleString()}</td>
                                <td>
                                    <button class="btn btn-danger" onclick="deleteFile(${file.id})">
                                        删除
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </table>
                `;
                document.getElementById('files-list').innerHTML = filesHtml;
            }
        }

        async function deleteUser(userId) {
            if (confirm('确定要删除这个用户吗？这将删除该用户的所有项目和文件！')) {
                const response = await fetchWithAuth(`${API_BASE}/admin/user/${userId}`, {
                    method: 'DELETE'
                });
                const data = await response.json();
                alert(data.message);
                if (data.success) {
                    loadUsers();
                    loadFiles();
                }
            }
        }

        async function deleteFile(fileId) {
            if (confirm('确定要删除这个文件吗？')) {
                const response = await fetchWithAuth(`${API_BASE}/admin/file/${fileId}`, {
                    method: 'DELETE'
                });
                const data = await response.json();
                alert(data.message);
                if (data.success) {
                    loadFiles();
                }
            }
        }

        // 初始化加载数据
        loadUsers();
        loadFiles();
    </script>
</body>
</html>''')

# 创建首页模板
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>Python IDE - 后端系统</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; text-align: center; }
        .login-form { margin: 20px auto; max-width: 300px; }
        input { margin: 5px; padding: 8px; width: 100%; }
        button { padding: 10px 20px; margin: 10px; }
    </style>
</head>
<body>
    <h1>Python IDE 后端系统</h1>
    <p>这是一个用于代码提交和管理的后端系统</p>

    <div class="login-form">
        <h3>管理员登录</h3>
        <input type="text" id="username" placeholder="用户名" value="admin">
        <input type="password" id="password" placeholder="密码" value="admin123">
        <button onclick="login()">登录</button>
    </div>

    <p>普通用户请使用 Python IDE 客户端进行登录和操作</p>

    <script>
        async function login() {
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

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
        }
    </script>
</body>
</html>''')

if __name__ == '__main__':
    # 确保上传目录存在
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    app.run(host='0.0.0.0', port=8081, debug=True)