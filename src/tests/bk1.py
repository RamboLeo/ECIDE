# app.py
# 单文件 Flask 应用：Python IDE 后端 + 管理面板（包含用户/文件/会话管理）
# 运行: python app.py
from flask import Flask, request, jsonify, send_file, render_template, abort
from werkzeug.utils import safe_join
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jwt
import datetime
import os
from functools import wraps
from sqlalchemy import or_
import mimetypes
import io

# ---------- 配置 ----------
APP_HOST = '0.0.0.0'
APP_PORT = 8081
DEBUG = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, 'user_projects')  # 存储上传文件的根目录
if not os.path.exists(UPLOAD_ROOT):
    os.makedirs(UPLOAD_ROOT, exist_ok=True)

app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'python_ide.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_ROOT
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 最大上传 200MB，可按需调整

db = SQLAlchemy(app)

# ---------- 数据库模型 ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # 方便管理面板展示
    display_name = db.Column(db.String(120), nullable=True)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    user = db.relationship('User', backref=db.backref('projects', lazy=True))


class CodeFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(1024), nullable=False)  # 存储路径相对于项目根或原始文件名
    content = db.Column(db.Text, nullable=True)            # 仅在可解码文本时保存
    is_binary = db.Column(db.Boolean, default=False)       # 是否为二进制文件
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    project = db.relationship('Project', backref=db.backref('files', lazy=True))
    user = db.relationship('User', backref=db.backref('files', lazy=True))


class LoginSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(512), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    user = db.relationship('User', backref=db.backref('sessions', lazy=True))

# ---------- 初始化 DB 与默认超级管理员 ----------
with app.app_context():
    db.create_all()
    # 创建超级管理员 mc/mc
    sa = User.query.filter_by(username='mc').first()
    if not sa:
        sa = User(username='mc', password_hash=generate_password_hash('mc'), is_admin=True, display_name='超级管理员 mc')
        db.session.add(sa)
        db.session.commit()

# ---------- 辅助函数 ----------
def create_jwt_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        'iat': datetime.datetime.utcnow()
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    # pyjwt 在不同版本返回 bytes 或 str，确保 str
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token

def get_authorization_token_from_header():
    token = request.headers.get('Authorization', '')
    if token.startswith('Bearer '):
        return token[7:]
    return token or None

def record_session_on_login(user, token):
    ip = request.remote_addr
    ua = request.headers.get('User-Agent', '')
    session = LoginSession(user_id=user.id, token=token, ip_address=ip, user_agent=ua, is_active=True)
    db.session.add(session)
    db.session.commit()
    return session

def deactivate_session(token):
    s = LoginSession.query.filter_by(token=token, is_active=True).first()
    if s:
        s.is_active = False
        db.session.commit()
        return True
    return False

def secure_path_join(base_folder, *paths):
    # 生成安全路径并确保它在 base_folder 内
    joined = os.path.abspath(os.path.join(base_folder, *paths))
    base = os.path.abspath(base_folder)
    if not joined.startswith(base + os.sep) and joined != base:
        raise Exception('非法路径访问')
    return joined

def save_uploaded_file_to_user(user, project_name, file_storage, file_path_in_project=None):
    username = user.username
    safe_project = secure_filename(project_name)
    base = os.path.join(app.config['UPLOAD_FOLDER'], username, safe_project)
    os.makedirs(base, exist_ok=True)
    # if file_path_in_project provided, respect subdirs
    if file_path_in_project:
        # normalize and secure each component
        parts = [secure_filename(p) for p in file_path_in_project.split('/') if p and p != '.']
        target_dir = os.path.join(base, *parts[:-1]) if len(parts) > 1 else base
        os.makedirs(target_dir, exist_ok=True)
        filename = parts[-1] if parts else secure_filename(file_storage.filename)
        filepath = os.path.join(target_dir, filename)
    else:
        filename = secure_filename(file_storage.filename)
        filepath = os.path.join(base, filename)

    file_storage.save(filepath)
    # try to read as text
    is_binary = False
    content_text = None
    try:
        with open(filepath, 'rb') as f:
            raw = f.read(1024*64)  # sample
            # attempt decode
            try:
                content_text = raw.decode('utf-8')
            except Exception:
                try:
                    content_text = raw.decode('gbk')
                except Exception:
                    content_text = None
        if content_text is None:
            is_binary = True
    except Exception:
        is_binary = True

    # record project and codefile
    project = Project.query.filter_by(name=project_name, user_id=user.id).first()
    if not project:
        project = Project(name=project_name, user_id=user.id)
        db.session.add(project)
        db.session.commit()
    relative_path = os.path.relpath(filepath, os.path.join(app.config['UPLOAD_FOLDER'], username, secure_project))
    codefile = CodeFile.query.filter_by(filename=relative_path, project_id=project.id).first()
    if not codefile:
        codefile = CodeFile(filename=relative_path, content=content_text if not is_binary else None,
                            is_binary=is_binary, project_id=project.id, user_id=user.id)
        db.session.add(codefile)
    else:
        codefile.updated_at = datetime.datetime.utcnow()
        codefile.is_binary = is_binary
        if not is_binary:
            codefile.content = content_text
    db.session.commit()
    return filepath, codefile

def build_disk_tree_for_user(user):
    user_root = os.path.join(app.config['UPLOAD_FOLDER'], user.username)
    if not os.path.exists(user_root):
        return {}
    tree = {}
    for project in os.listdir(user_root):
        project_dir = os.path.join(user_root, project)
        if not os.path.isdir(project_dir):
            continue
        tree[project] = []
        for root, dirs, files in os.walk(project_dir):
            rel_root = os.path.relpath(root, project_dir)
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.join(rel_root, f) if rel_root != '.' else f
                tree[project].append(rel)
    return tree

# ---------- 验证装饰器 ----------
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_authorization_token_from_header()
        if not token:
            return jsonify({'success': False, 'message': 'Token缺失'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                raise Exception('用户不存在')
            # 检查会话是否存在且激活
            session = LoginSession.query.filter_by(token=token, is_active=True).first()
            if not session:
                return jsonify({'success': False, 'message': '会话已失效或请重新登录'}), 401
            # 更新最后活动时间
            session.last_active = datetime.datetime.utcnow()
            db.session.commit()
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token过期'}), 401
        except Exception as e:
            return jsonify({'success': False, 'message': f'Token无效: {str(e)}'}), 401

        return f(current_user, token, *args, **kwargs)

    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(current_user, token, *args, **kwargs):
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': '需要管理员权限'}), 403
        return f(current_user, token, *args, **kwargs)
    return decorated

# ---------- 公共 API: 注册 / 登录 / 登出 / 修改密码 ----------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(force=True)
    username = (data.get('username') or '').strip()
    password = data.get('password')
    display = data.get('display_name', None)
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'})
    user = User(username=username, password_hash=generate_password_hash(password), display_name=display)
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'message': '注册成功', 'user': {'id': user.id, 'username': user.username}})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(force=True)
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名或密码不能为空'}), 400
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
    token = create_jwt_token(user.id)
    record_session_on_login(user, token)
    return jsonify({
        'success': True,
        'token': token,
        'user': {'id': user.id, 'username': user.username, 'is_admin': user.is_admin}
    })

@app.route('/api/logout', methods=['POST'])
@token_required
def logout(current_user, token):
    deactivate_session(token)
    return jsonify({'success': True, 'message': '已登出'})

@app.route('/api/user/change_password', methods=['POST'])
@token_required
def change_password(current_user, token):
    data = request.get_json(force=True)
    old = data.get('old_password')
    new = data.get('new_password')
    if not old or not new:
        return jsonify({'success': False, 'message': '参数不完整'}), 400
    if not check_password_hash(current_user.password_hash, old):
        return jsonify({'success': False, 'message': '旧密码错误'}), 401
    current_user.password_hash = generate_password_hash(new)
    db.session.commit()
    return jsonify({'success': True, 'message': '密码已更新'})

# ---------- 客户端：提交代码/文件（支持任意类型） ----------
@app.route('/api/submit_code', methods=['POST'])
@token_required
def submit_code(current_user, token):
    # 支持 JSON 提交（文本内容） 或 multipart/form-data 文件上传
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        # 文件上传
        project_name = request.form.get('project_name') or 'default'
        file_path = request.form.get('file_path')  # 可选：项目内部路径，如 src/main.py
        file = request.files.get('file')
        if not file:
            return jsonify({'success': False, 'message': '未包含文件'}), 400
        filepath, codefile = save_uploaded_file_to_user(current_user, project_name, file, file_path_in_project=file_path)
        return jsonify({'success': True, 'message': '文件上传成功', 'path': filepath})
    else:
        data = request.get_json(force=True)
        project_name = data.get('project_name') or 'default'
        file_path = data.get('file_path') or 'main.py'
        code_content = data.get('code_content')
        if code_content is None:
            return jsonify({'success': False, 'message': 'code_content 为空'}), 400
        # 保存到 DB，并同时写到磁盘以便管理面板显示（文本）
        project = Project.query.filter_by(name=project_name, user_id=current_user.id).first()
        if not project:
            project = Project(name=project_name, user_id=current_user.id)
            db.session.add(project)
            db.session.commit()
        # ensure dir
        user_dir = os.path.join(app.config['UPLOAD_FOLDER'], current_user.username, secure_filename(project_name))
        os.makedirs(user_dir, exist_ok=True)
        safe_fp = secure_filename(file_path)
        disk_path = os.path.join(user_dir, safe_fp)
        with open(disk_path, 'w', encoding='utf-8') as f:
            f.write(code_content)
        rel = os.path.relpath(disk_path, os.path.join(app.config['UPLOAD_FOLDER'], current_user.username, secure_filename(project_name)))
        codefile = CodeFile.query.filter_by(filename=rel, project_id=project.id).first()
        if codefile:
            codefile.content = code_content
            codefile.updated_at = datetime.datetime.utcnow()
            codefile.is_binary = False
        else:
            codefile = CodeFile(filename=rel, content=code_content, is_binary=False, project_id=project.id, user_id=current_user.id)
            db.session.add(codefile)
        db.session.commit()
        return jsonify({'success': True, 'message': '代码提交成功', 'file_id': codefile.id})

# ---------- 读取项目、文件内容（普通用户） ----------
@app.route('/api/projects', methods=['GET'])
@token_required
def get_projects(current_user, token):
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
def get_project_files(current_user, token, project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权访问此项目'}), 403
    files = CodeFile.query.filter_by(project_id=project_id).all()
    result = []
    for file in files:
        result.append({
            'id': file.id,
            'filename': file.filename,
            'is_binary': file.is_binary,
            'created_at': file.created_at.isoformat(),
            'updated_at': file.updated_at.isoformat()
        })
    return jsonify({'success': True, 'files': result})

@app.route('/api/file/<int:file_id>', methods=['GET'])
@token_required
def get_file_content(current_user, token, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    if code_file.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权访问此文件'}), 403
    # try serve disk file if binary or if content missing
    user_proj_root = os.path.join(app.config['UPLOAD_FOLDER'], code_file.user.username, secure_filename(code_file.project.name))
    possible_disk = os.path.join(user_proj_root, code_file.filename)
    if code_file.is_binary or code_file.content is None:
        if os.path.exists(possible_disk):
            return send_file(possible_disk, as_attachment=True)
        else:
            return jsonify({'success': False, 'message': '磁盘文件丢失，无法在线查看'}), 404
    else:
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
def delete_file(current_user, token, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    if code_file.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权删除此文件'}), 403
    # also attempt to remove disk file if present
    user_proj_root = os.path.join(app.config['UPLOAD_FOLDER'], code_file.user.username, secure_filename(code_file.project.name))
    possible_disk = os.path.join(user_proj_root, code_file.filename)
    try:
        if os.path.exists(possible_disk):
            os.remove(possible_disk)
    except Exception:
        pass
    db.session.delete(code_file)
    db.session.commit()
    return jsonify({'success': True, 'message': '文件删除成功'})

# ---------- 管理员接口（在 admin 页面使用） ----------
@app.route('/api/admin/users', methods=['GET'])
@token_required
@admin_required
def admin_get_users(current_user, token):
    # 支持检索 ?q=xxx & status=online|offline|all
    q = request.args.get('q', '').strip()
    status = request.args.get('status', 'all')
    query = User.query
    if q:
        query = query.filter(or_(User.username.like(f'%{q}%'), (User.display_name != None) & (User.display_name.like(f'%{q}%')) ))
    users = query.all()
    result = []
    for u in users:
        # determine online status by active sessions
        active_sessions = LoginSession.query.filter_by(user_id=u.id, is_active=True).count()
        is_online = active_sessions > 0
        if status == 'online' and not is_online:
            continue
        if status == 'offline' and is_online:
            continue
        result.append({
            'id': u.id,
            'username': u.username,
            'display_name': u.display_name,
            'is_admin': u.is_admin,
            'created_at': u.created_at.isoformat(),
            'project_count': len(u.projects),
            'file_count': len(u.files),
            'is_online': is_online
        })
    return jsonify({'success': True, 'users': result})

@app.route('/api/admin/user', methods=['POST'])
@token_required
@admin_required
def admin_create_user(current_user, token):
    data = request.get_json(force=True)
    username = (data.get('username') or '').strip()
    password = data.get('password') or '123456'
    is_admin_flag = bool(data.get('is_admin', False))
    display = data.get('display_name', None)
    if not username:
        return jsonify({'success': False, 'message': '用户名不能为空'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'}), 400
    user = User(username=username, password_hash=generate_password_hash(password), is_admin=is_admin_flag, display_name=display)
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'message': '用户创建成功', 'user': {'id': user.id, 'username': user.username}})

@app.route('/api/admin/user/<int:user_id>', methods=['PUT'])
@token_required
@admin_required
def admin_update_user(current_user, token, user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json(force=True)
    if 'password' in data and data['password']:
        user.password_hash = generate_password_hash(data['password'])
    if 'is_admin' in data:
        user.is_admin = bool(data['is_admin'])
    if 'display_name' in data:
        user.display_name = data.get('display_name')
    db.session.commit()
    return jsonify({'success': True, 'message': '用户信息已更新'})

@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@token_required
@admin_required
def admin_delete_user(current_user, token, user_id):
    if current_user.id == user_id:
        return jsonify({'success': False, 'message': '不能删除自己的账户'}), 400
    user = User.query.get_or_404(user_id)
    # 删除用户的所有会话、文件、项目以及磁盘目录
    LoginSession.query.filter_by(user_id=user_id).delete()
    CodeFile.query.filter_by(user_id=user_id).delete()
    Project.query.filter_by(user_id=user_id).delete()
    # delete disk files
    user_dir = os.path.join(app.config['UPLOAD_FOLDER'], user.username)
    try:
        if os.path.exists(user_dir):
            # remove tree safely
            import shutil
            shutil.rmtree(user_dir)
    except Exception:
        pass
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': '用户删除成功'})

@app.route('/api/admin/files', methods=['GET'])
@token_required
@admin_required
def admin_get_all_files(current_user, token):
    # 支持按用户名过滤 ?username=xxx
    username = request.args.get('username', '').strip()
    q = CodeFile.query
    if username:
        u = User.query.filter_by(username=username).first()
        if not u:
            return jsonify({'success': True, 'files': []})
        q = q.filter_by(user_id=u.id)
    files = q.all()
    result = []
    for file in files:
        project_name = file.project.name if file.project else ''
        result.append({
            'id': file.id,
            'filename': file.filename,
            'is_binary': file.is_binary,
            'user_id': file.user_id,
            'username': file.user.username,
            'project_id': file.project_id,
            'project_name': project_name,
            'created_at': file.created_at.isoformat(),
            'updated_at': file.updated_at.isoformat()
        })
    return jsonify({'success': True, 'files': result})

@app.route('/api/admin/file/<int:file_id>', methods=['DELETE'])
@token_required
@admin_required
def admin_delete_file(current_user, token, file_id):
    code_file = CodeFile.query.get_or_404(file_id)
    # remove disk file if exists
    user_proj_root = os.path.join(app.config['UPLOAD_FOLDER'], code_file.user.username, secure_filename(code_file.project.name))
    possible_disk = os.path.join(user_proj_root, code_file.filename)
    try:
        if os.path.exists(possible_disk):
            os.remove(possible_disk)
    except Exception:
        pass
    db.session.delete(code_file)
    db.session.commit()
    return jsonify({'success': True, 'message': '文件删除成功'})

@app.route('/api/admin/download_file', methods=['GET'])
@token_required
@admin_required
def admin_download_file(current_user, token):
    # ?username=&project=&path=
    username = request.args.get('username')
    project = request.args.get('project')
    path = request.args.get('path')
    if not all([username, project, path]):
        return jsonify({'success': False, 'message': '参数不完整'}), 400
    try:
        file_on_disk = secure_path_join(app.config['UPLOAD_FOLDER'], username, secure_filename(project), path)
    except Exception as e:
        return jsonify({'success': False, 'message': '非法文件路径'}), 400
    if not os.path.exists(file_on_disk):
        return jsonify({'success': False, 'message': '文件不存在'}), 404
    return send_file(file_on_disk, as_attachment=True)

@app.route('/api/admin/user/<int:user_id>/projects_files', methods=['GET'])
@token_required
@admin_required
def admin_user_projects_files(current_user, token, user_id):
    # 返回 DB 中的项目、文件，以及磁盘目录树
    user = User.query.get_or_404(user_id)
    proj_list = []
    for p in Project.query.filter_by(user_id=user.id).all():
        files = []
        for f in CodeFile.query.filter_by(project_id=p.id).all():
            files.append({
                'id': f.id,
                'filename': f.filename,
                'is_binary': f.is_binary,
                'created_at': f.created_at.isoformat(),
                'updated_at': f.updated_at.isoformat()
            })
        proj_list.append({'id': p.id, 'name': p.name, 'files': files})
    disk_tree = build_disk_tree_for_user(user)
    return jsonify({'success': True, 'db_projects': proj_list, 'disk_tree': disk_tree})

@app.route('/api/admin/sessions', methods=['GET'])
@token_required
@admin_required
def admin_get_sessions(current_user, token):
    # 支持 ?username=&active=1|0
    username = request.args.get('username', '').strip()
    active = request.args.get('active', None)
    q = LoginSession.query
    if username:
        u = User.query.filter_by(username=username).first()
        if not u:
            return jsonify({'success': True, 'sessions': []})
        q = q.filter_by(user_id=u.id)
    if active is not None:
        q = q.filter_by(is_active=(active == '1' or active.lower()=='true'))
    sessions = q.order_by(LoginSession.last_active.desc()).all()
    result = []
    for s in sessions:
        result.append({
            'id': s.id,
            'user_id': s.user_id,
            'username': s.user.username,
            'created_at': s.created_at.isoformat(),
            'last_active': s.last_active.isoformat(),
            'is_active': s.is_active,
            'ip_address': s.ip_address,
            'user_agent': s.user_agent
        })
    return jsonify({'success': True, 'sessions': result})

@app.route('/api/admin/session/<int:session_id>/deactivate', methods=['POST'])
@token_required
@admin_required
def admin_deactivate_session(current_user, token, session_id):
    s = LoginSession.query.get_or_404(session_id)
    s.is_active = False
    db.session.commit()
    return jsonify({'success': True, 'message': '会话已下线'})

# ---------- 管理面板页面（单页多标签） ----------
@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')

@app.route('/')
def index():
    return render_template('index.html')

# ---------- 自动写入模板（如果 templates 不存在则创建） ----------
if not os.path.exists(os.path.join(BASE_DIR, 'templates')):
    os.makedirs(os.path.join(BASE_DIR, 'templates'), exist_ok=True)

# 管理员页面（美观分区、检索、会话与文件浏览）
admin_html = r'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Python IDE - 管理员面板</title>
    <style>
        body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; margin: 0; background: #f6f8fa; color:#222; }
        header { background: linear-gradient(90deg,#0f172a,#0b1220); color: white; padding: 18px 24px; }
        header h1 { margin: 0; font-size: 20px; }
        .container { display: flex; height: calc(100vh - 64px); }
        nav { width: 260px; background: #0f172a; color: #cbd5e1; padding: 16px; box-sizing: border-box; }
        nav .section { margin-bottom: 18px; }
        nav button { width: 100%; padding: 10px; border: none; background: transparent; color: inherit; text-align:left; border-radius:8px; cursor:pointer; }
        nav button.active { background: rgba(255,255,255,0.06); }
        main { flex:1; padding: 20px; overflow:auto; }
        .card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(15,23,42,0.06); margin-bottom:16px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px 10px; border-bottom: 1px solid #eef2f7; text-align: left; font-size:13px; }
        th { color:#334155; font-weight:600; }
        .btn { padding:6px 10px; border-radius:8px; cursor:pointer; border:none; }
        .btn-danger { background:#ef4444; color:white; }
        .btn-primary { background:#2563eb; color:white; }
        .flex { display:flex; gap:8px; align-items:center; }
        input[type="text"], input[type="password"], select { padding:8px 10px; border-radius:8px; border:1px solid #e6eef6; width:220px; }
        .small { font-size:12px; color:#64748b; }
        .tag { font-size:12px; padding:4px 6px; border-radius:6px; background:#eef2ff; color:#1e3a8a; }
        pre { background:#0b1220; color:#dbeafe; padding:12px; border-radius:8px; overflow:auto; max-height:360px; }
    </style>
</head>
<body>
    <header>
        <h1>Python IDE 管理员面板（超级管理员）</h1>
    </header>
    <div class="container">
        <nav>
            <div class="section">
                <button id="tab-users" class="active" onclick="showTab('users')">用户管理</button>
            </div>
            <div class="section">
                <button id="tab-files" onclick="showTab('files')">文件 & 项目</button>
            </div>
            <div class="section">
                <button id="tab-sessions" onclick="showTab('sessions')">会话管理（登录状态）</button>
            </div>
            <div class="section">
                <button id="tab-search" onclick="showTab('search')">快速检索</button>
            </div>
            <div style="margin-top:18px" class="small">当前 Token 存储于 localStorage（管理员登录后可使用）。</div>
        </nav>
        <main>
            <!-- 用户管理 -->
            <div id="panel-users" class="card panel">
                <h3>用户管理</h3>
                <div style="margin-bottom:12px;" class="flex">
                    <input type="text" id="q-users" placeholder="按用户名或显示名检索">
                    <select id="filter-status"><option value="all">所有</option><option value="online">在线</option><option value="offline">离线</option></select>
                    <button class="btn btn-primary" onclick="loadUsers()">检索</button>
                    <button class="btn" onclick="showCreateUser()">新增用户</button>
                </div>
                <div id="users-list"></div>
                <div id="create-user-form" style="display:none; margin-top:12px;">
                    <h4>创建新用户</h4>
                    <div class="flex">
                        <input id="new-username" placeholder="用户名">
                        <input id="new-password" placeholder="密码">
                        <select id="new-is-admin"><option value="0">普通用户</option><option value="1">管理员</option></select>
                        <input id="new-display" placeholder="显示名（可选）">
                        <button class="btn btn-primary" onclick="createUser()">创建</button>
                    </div>
                </div>
            </div>

            <!-- 文件管理 -->
            <div id="panel-files" class="card panel" style="display:none;">
                <h3>文件 & 项目管理</h3>
                <div class="flex" style="margin-bottom:12px;">
                    <input id="files-username" placeholder="检索用户名（可空）">
                    <button class="btn btn-primary" onclick="loadFiles()">加载文件</button>
                    <button class="btn" onclick="refreshDisk()">刷新磁盘树</button>
                </div>
                <div id="files-list"></div>
                <hr>
                <h4>查看指定用户的项目与磁盘树</h4>
                <div class="flex">
                    <input id="inspect-username" placeholder="用户名">
                    <button class="btn btn-primary" onclick="inspectUser()">查看</button>
                </div>
                <div id="inspect-result" style="margin-top:12px;"></div>
            </div>

            <!-- 会话管理 -->
            <div id="panel-sessions" class="card panel" style="display:none;">
                <h3>会话管理（登录状态）</h3>
                <div class="flex" style="margin-bottom:12px;">
                    <input id="session-username" placeholder="按用户名检索">
                    <select id="session-active"><option value="">全部</option><option value="1">仅在线</option><option value="0">仅离线</option></select>
                    <button class="btn btn-primary" onclick="loadSessions()">检索</button>
                </div>
                <div id="sessions-list"></div>
            </div>

            <!-- 检索 -->
            <div id="panel-search" class="card panel" style="display:none;">
                <h3>快速检索</h3>
                <div class="flex" style="margin-bottom:12px;">
                    <input id="global-q" placeholder="用户名、文件名、项目名">
                    <button class="btn btn-primary" onclick="globalSearch()">搜索用户 / 文件</button>
                </div>
                <div id="search-result"></div>
            </div>
        </main>
    </div>

<script>
const API_BASE = '/api';
let token = localStorage.getItem('token');

if (!token) {
    // 未登录则提示通过首页登录
    alert('请先以管理员账号登录（在首页登录后会跳转到 /admin）。默认超级管理员: mc/mc');
    window.location.href = '/';
}

function authHeaders() {
    return {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
    };
}

async function fetchWithAuth(url, options = {}) {
    options.headers = {...options.headers, ...authHeaders()};
    const resp = await fetch(url, options);
    if (resp.status === 401) {
        localStorage.removeItem('token');
        alert('Token 失效或未登录，请重新登录');
        window.location.href = '/';
    }
    return resp;
}

function showTab(key) {
    document.querySelectorAll('.panel').forEach(n=>n.style.display='none');
    document.getElementById('panel-' + key).style.display = 'block';
    document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active'));
    document.getElementById('tab-' + key).classList.add('active');
}

async function loadUsers() {
    const q = document.getElementById('q-users').value;
    const status = document.getElementById('filter-status').value;
    const url = `${API_BASE}/admin/users?q=${encodeURIComponent(q)}&status=${status}`;
    const r = await fetchWithAuth(url);
    const data = await r.json();
    if (!data.success) { alert(data.message || '加载失败'); return; }
    const html = `
        <table>
            <tr><th>ID</th><th>用户名</th><th>显示名</th><th>管理员</th><th>在线</th><th>项目数</th><th>文件数</th><th>操作</th></tr>
            ${data.users.map(u=> \`
                <tr>
                    <td>\${u.id}</td>
                    <td>\${u.username}</td>
                    <td>\${u.display_name||''}</td>
                    <td>\${u.is_admin? '是':'否'}</td>
                    <td>\${u.is_online? '<span class="tag">在线</span>':'离线'}</td>
                    <td>\${u.project_count}</td>
                    <td>\${u.file_count}</td>
                    <td>
                        <button class="btn" onclick="editUser(\${u.id})">编辑</button>
                        ${'${'}u.is_admin? '' : '<button class="btn btn-danger" onclick="deleteUser('+u.id+')">删除</button>'}
                        <button class="btn" onclick="inspectUser(\${u.username})">查看项目</button>
                    </td>
                </tr>
            \`).join('')}
        </table>
    `;
    document.getElementById('users-list').innerHTML = html;
}

function showCreateUser() {
    const el = document.getElementById('create-user-form');
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

async function createUser() {
    const username = document.getElementById('new-username').value;
    const password = document.getElementById('new-password').value;
    const is_admin = document.getElementById('new-is-admin').value;
    const display = document.getElementById('new-display').value;
    const payload = { username, password, is_admin: Number(is_admin), display_name: display };
    const r = await fetchWithAuth(API_BASE + '/admin/user', { method: 'POST', body: JSON.stringify(payload) });
    const d = await r.json();
    alert(d.message || JSON.stringify(d));
    if (d.success) {
        loadUsers();
        document.getElementById('new-username').value='';
        document.getElementById('new-password').value='';
    }
}

async function editUser(id) {
    const newpass = prompt('输入新密码（留空表示不修改）');
    const is_admin = confirm('是否设为管理员？(确定=是)') ? 1 : 0;
    const display = prompt('显示名（可留空）','');
    const payload = {};
    if (newpass) payload.password = newpass;
    payload.is_admin = is_admin;
    payload.display_name = display;
    const r = await fetchWithAuth(API_BASE + '/admin/user/' + id, { method: 'PUT', body: JSON.stringify(payload) });
    const d = await r.json();
    alert(d.message || JSON.stringify(d));
    loadUsers();
}

async function deleteUser(id) {
    if (!confirm('确定删除该用户？此操作会移除该用户所有文件与项目，并删除磁盘目录！')) return;
    const r = await fetchWithAuth(API_BASE + '/admin/user/' + id, { method: 'DELETE' });
    const d = await r.json();
    alert(d.message || JSON.stringify(d));
    loadUsers();
    loadFiles();
}

async function loadFiles() {
    const username = document.getElementById('files-username').value;
    const url = API_BASE + '/admin/files' + (username ? '?username=' + encodeURIComponent(username) : '');
    const r = await fetchWithAuth(url);
    const d = await r.json();
    if (!d.success) { alert(d.message || '加载失败'); return; }
    const html = `
        <table>
            <tr><th>ID</th><th>文件名</th><th>用户</th><th>项目</th><th>二进制</th><th>创建</th><th>更新时间</th><th>操作</th></tr>
            ${d.files.map(f=> \`
                <tr>
                    <td>\${f.id}</td>
                    <td>\${f.filename}</td>
                    <td>\${f.username} (ID:\${f.user_id})</td>
                    <td>\${f.project_name||''}</td>
                    <td>\${f.is_binary? '是':'否'}</td>
                    <td>\${new Date(f.created_at).toLocaleString()}</td>
                    <td>\${new Date(f.updated_at).toLocaleString()}</td>
                    <td>
                        <button class="btn" onclick="downloadById(\${f.id})">下载/查看</button>
                        <button class="btn btn-danger" onclick="adminDeleteFile(\${f.id})">删除</button>
                    </td>
                </tr>
            \`).join('')}
        </table>
    `;
    document.getElementById('files-list').innerHTML = html;
}

async function downloadById(id) {
    // 先请求 /api/file/:id 会在后台判断权限并返回文件或内容
    const r = await fetchWithAuth(API_BASE + '/file/' + id);
    if (r.headers.get('content-disposition')) {
        // binary download
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'file';
        a.click();
        URL.revokeObjectURL(url);
    } else {
        const d = await r.json();
        if (d.success && d.file) {
            const win = window.open('', '_blank');
            win.document.write('<pre>' + escapeHtml(d.file.content) + '</pre>');
        } else {
            alert(d.message || '无法打开文件');
        }
    }
}

async function adminDeleteFile(id) {
    if (!confirm('确定要删除该文件吗？')) return;
    const r = await fetchWithAuth(API_BASE + '/admin/file/' + id, { method: 'DELETE' });
    const d = await r.json();
    alert(d.message || JSON.stringify(d));
    loadFiles();
}

function escapeHtml(s) { return s ? s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : ''; }

async function inspectUser(username) {
    if (!username) username = document.getElementById('inspect-username').value;
    if (!username) { alert('请输入用户名'); return; }
    // find user id via users list call
    const r1 = await fetchWithAuth(API_BASE + '/admin/users?q=' + encodeURIComponent(username));
    const d1 = await r1.json();
    if (!d1.success) { alert('用户检索失败'); return; }
    const u = d1.users.find(x => x.username === username) || d1.users[0];
    if (!u) { alert('用户不存在'); return; }
    const r = await fetchWithAuth(API_BASE + '/admin/user/' + u.id + '/projects_files');
    const d = await r.json();
    if (!d.success) { alert(d.message || '加载失败'); return; }
    let html = '<h4>DB 项目</h4>';
    if (d.db_projects.length === 0) html += '<div class="small">无项目</div>';
    else {
        html += '<table><tr><th>项目名</th><th>文件</th></tr>';
        d.db_projects.forEach(p => {
            html += '<tr><td>' + p.name + '</td><td>' + (p.files.map(f=>('<div>' + f.filename + (f.is_binary? ' <span class="tag">二进制</span>':'') + '</div>')).join('')) + '</td></tr>';
        });
        html += '</table>';
    }
    html += '<h4>磁盘树</h4>';
    if (!d.disk_tree || Object.keys(d.disk_tree).length === 0) html += '<div class="small">无磁盘文件</div>';
    else {
        for (const p of Object.keys(d.disk_tree)) {
            html += '<div style="margin-top:8px;"><strong>' + p + '</strong><div class="small">' + d.disk_tree[p].slice(0,200).map(it=>('<div>' + it + ' <button class="btn" onclick="downloadPath(\''+username+'\', \''+p+'\', \''+ encodeURIComponent(it) +'\')">下载</button></div>')).join('') + '</div></div>';
        }
    }
    document.getElementById('inspect-result').innerHTML = html;
}

async function downloadPath(username, project, pathenc) {
    const path = decodeURIComponent(pathenc);
    const url = API_BASE + '/admin/download_file?username=' + encodeURIComponent(username) + '&project=' + encodeURIComponent(project) + '&path=' + encodeURIComponent(path);
    const r = await fetchWithAuth(url);
    if (r.status !== 200) {
        const d = await r.json();
        alert(d.message || '下载失败');
        return;
    }
    const blob = await r.blob();
    const dlUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = dlUrl;
    a.download = path.split('/').pop();
    a.click();
    URL.revokeObjectURL(dlUrl);
}

async function refreshDisk() {
    alert('磁盘树会在"查看指定用户的项目与磁盘树"处显示；这里点击"查看"以刷新指定用户。');
}

async function loadSessions() {
    const username = document.getElementById('session-username').value;
    const active = document.getElementById('session-active').value;
    const q = API_BASE + '/admin/sessions?username=' + encodeURIComponent(username) + (active !== '' ? '&active=' + active : '');
    const r = await fetchWithAuth(q);
    const d = await r.json();
    if (!d.success) { alert(d.message || '加载失败'); return; }
    const html = `
        <table>
            <tr><th>ID</th><th>用户名</th><th>创建</th><th>最后活动</th><th>是否在线</th><th>IP</th><th>UA</th><th>操作</th></tr>
            ${d.sessions.map(s=> \`
                <tr>
                    <td>\${s.id}</td>
                    <td>\${s.username}</td>
                    <td>\${new Date(s.created_at).toLocaleString()}</td>
                    <td>\${new Date(s.last_active).toLocaleString()}</td>
                    <td>\${s.is_active? '<span class="tag">在线</span>':'离线'}</td>
                    <td>\${s.ip_address || ''}</td>
                    <td style="max-width:360px; overflow:auto;">\${s.user_agent || ''}</td>
                    <td><button class="btn btn-danger" onclick="deactivateSession(\${s.id})">下线</button></td>
                </tr>
            \`).join('')}
        </table>
    `;
    document.getElementById('sessions-list').innerHTML = html;
}

async function deactivateSession(id) {
    if (!confirm('确定要下线这个会话？')) return;
    const r = await fetchWithAuth(API_BASE + '/admin/session/' + id + '/deactivate', { method: 'POST' });
    const d = await r.json();
    alert(d.message || JSON.stringify(d));
    loadSessions();
}

async function globalSearch() {
    const q = document.getElementById('global-q').value;
    if (!q) { alert('请输入关键词'); return; }
    // 搜索用户
    const ru = await fetchWithAuth(API_BASE + '/admin/users?q=' + encodeURIComponent(q));
    const du = await ru.json();
    let html = '<h4>用户</h4>';
    if (du.users.length === 0) html += '<div class="small">无匹配用户</div>';
    else html += '<div>' + du.users.map(u=>('<div>' + u.username + ' (' + (u.display_name||'') + ') <button class="btn" onclick="inspectUser(\\''+u.username+'\\')">查看</button></div>')).join('') + '</div>';
    // 搜索文件 by listing all files and filter client-side (简单实现)
    const rf = await fetchWithAuth(API_BASE + '/admin/files');
    const df = await rf.json();
    const matched = (df.files || []).filter(f => f.filename.indexOf(q) !== -1 || (f.project_name || '').indexOf(q) !== -1 || (f.username || '').indexOf(q) !== -1);
    html += '<h4>文件匹配</h4>';
    if (matched.length === 0) html += '<div class="small">无匹配文件</div>';
    else html += '<div>' + matched.map(m=>('<div>' + m.username + ' / ' + m.project_name + ' / ' + m.filename + ' <button class="btn" onclick="downloadById('+m.id+')">下载</button></div>')).join('') + '</div>';
    document.getElementById('search-result').innerHTML = html;
}

// 初始化
loadUsers();
</script>
</body>
</html>
'''

index_html = r'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Python IDE 后端系统</title>
  <style>
    body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial; padding:40px; background:#f3f6fb; color:#112; }
    .card { background:white; padding:20px; border-radius:12px; max-width:560px; margin:auto; box-shadow:0 6px 18px rgba(15,23,42,0.06); }
    input { padding:10px 12px; border-radius:8px; border:1px solid #e6eef6; width:100%; margin-top:8px; box-sizing:border-box; }
    button { padding:10px 14px; border-radius:8px; border:none; background:#2563eb; color:white; margin-top:12px; cursor:pointer; width:100%; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Python IDE 后端系统</h2>
    <p>用于代码提交与管理员管理。请用管理员账号登录以访问管理面板。</p>
    <div>
      <label>用户名</label>
      <input id="username" value="mc">
      <label>密码</label>
      <input id="password" type="password" value="mc">
      <button onclick="login()">登录并进入管理员面板</button>
    </div>
  </div>
<script>
async function login() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const r = await fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ username, password }) });
    const d = await r.json();
    if (d.success) {
        localStorage.setItem('token', d.token);
        alert('登录成功，跳转管理员面板');
        location.href = '/admin';
    } else {
        alert('登录失败: ' + (d.message || ''));
    }
}
</script>
</body>
</html>
'''

with open(os.path.join(BASE_DIR, 'templates', 'admin.html'), 'w', encoding='utf-8') as f:
    f.write(admin_html)

with open(os.path.join(BASE_DIR, 'templates', 'index.html'), 'w', encoding='utf-8') as f:
    f.write(index_html)

# ---------- 启动 ----------
if __name__ == '__main__':
    # ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print("Server starting at http://127.0.0.1:%d" % APP_PORT)
    app.run(host=APP_HOST, port=APP_PORT, debug=DEBUG)
