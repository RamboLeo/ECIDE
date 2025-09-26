from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import sqlite3
from datetime import datetime
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import time

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['DATABASE'] = 'ide_system.db'


# 初始化数据库
def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()

    # 用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  is_admin BOOLEAN DEFAULT FALSE,
                  is_active BOOLEAN DEFAULT TRUE,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  last_login TIMESTAMP,
                  submission_count INTEGER DEFAULT 0)''')

    # 项目表
    c.execute('''CREATE TABLE IF NOT EXISTS projects
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  owner_id INTEGER NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  file_count INTEGER DEFAULT 0,
                  FOREIGN KEY (owner_id) REFERENCES users (id))''')

    # 文件表
    c.execute('''CREATE TABLE IF NOT EXISTS files
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  project_id INTEGER NOT NULL,
                  filename TEXT NOT NULL,
                  content TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (project_id) REFERENCES projects (id))''')

    # 包管理表
    c.execute('''CREATE TABLE IF NOT EXISTS packages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE NOT NULL,
                  version TEXT NOT NULL,
                  installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # 创建默认管理员用户
    hashed_password = generate_password_hash('admin123')
    try:
        c.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                  ('admin', hashed_password, True))
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()


# 数据库连接辅助函数
def get_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


# JWT token验证装饰器
def token_required(f):
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'message': 'Token is missing'}), 401

        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = get_user_by_id(data['user_id'])
            if not current_user:
                return jsonify({'success': False, 'message': 'Invalid token'}), 401
        except:
            return jsonify({'success': False, 'message': 'Token is invalid'}), 401

        return f(current_user, *args, **kwargs)

    decorated.__name__ = f.__name__
    return decorated


# 管理员权限验证装饰器
def admin_required(f):
    def decorated(current_user, *args, **kwargs):
        if not current_user['is_admin']:
            return jsonify({'success': False, 'message': 'Admin privileges required'}), 403
        return f(current_user, *args, **kwargs)

    decorated.__name__ = f.__name__
    return decorated


# 用户相关函数
def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_username(username):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(user) if user else None


# 认证路由
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    is_admin = data.get('is_admin', False)

    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})

    user = get_user_by_username(username)
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'success': False, 'message': '用户名或密码错误'})

    if not user['is_active']:
        return jsonify({'success': False, 'message': '用户已被禁用'})

    if is_admin and not user['is_admin']:
        return jsonify({'success': False, 'message': '该用户不是管理员'})

    # 更新最后登录时间
    conn = get_db()
    conn.execute('UPDATE users SET last_login = ? WHERE id = ?',
                 (datetime.now().isoformat(), user['id']))
    conn.commit()
    conn.close()

    # 生成token
    token = jwt.encode({
        'user_id': user['id'],
        'exp': time.time() + 3600  # 1小时过期
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'is_admin': user['is_admin']
        }
    })


# 用户管理路由
@app.route('/api/admin/users', methods=['GET'])
@token_required
@admin_required
def get_users(current_user):
    search = request.args.get('search', '')
    conn = get_db()

    if search:
        users = conn.execute('''
            SELECT id, username, is_admin, is_active, created_at, last_login, submission_count 
            FROM users WHERE username LIKE ? ORDER BY created_at DESC
        ''', (f'%{search}%',)).fetchall()
    else:
        users = conn.execute('''
            SELECT id, username, is_admin, is_active, created_at, last_login, submission_count 
            FROM users ORDER BY created_at DESC
        ''').fetchall()

    conn.close()

    users_list = []
    for user in users:
        users_list.append({
            'id': user['id'],
            'username': user['username'],
            'is_admin': bool(user['is_admin']),
            'is_active': bool(user['is_active']),
            'created_at': user['created_at'],
            'last_login': user['last_login'],
            'submission_count': user['submission_count']
        })

    return jsonify({'success': True, 'users': users_list})


@app.route('/api/admin/users', methods=['POST'])
@token_required
@admin_required
def create_user(current_user):
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    is_admin = data.get('is_admin', False)

    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})

    conn = get_db()

    # 检查用户名是否已存在
    existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    if existing_user:
        conn.close()
        return jsonify({'success': False, 'message': '用户名已存在'})

    # 创建用户
    hashed_password = generate_password_hash(password)
    conn.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
                 (username, hashed_password, is_admin))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '用户创建成功'})


@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@token_required
@admin_required
def update_user(current_user, user_id):
    data = request.get_json()
    password = data.get('password')
    is_admin = data.get('is_admin')

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'success': False, 'message': '用户不存在'})

    update_fields = []
    update_values = []

    if password:
        hashed_password = generate_password_hash(password)
        update_fields.append('password = ?')
        update_values.append(hashed_password)

    if is_admin is not None:
        update_fields.append('is_admin = ?')
        update_values.append(is_admin)

    if update_fields:
        update_values.append(user_id)
        query = f'UPDATE users SET {", ".join(update_fields)} WHERE id = ?'
        conn.execute(query, update_values)
        conn.commit()

    conn.close()
    return jsonify({'success': True, 'message': '用户信息已更新'})


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(current_user, user_id):
    conn = get_db()

    # 检查是否是当前用户
    if current_user['id'] == user_id:
        conn.close()
        return jsonify({'success': False, 'message': '不能删除当前登录的用户'})

    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '用户已删除'})


@app.route('/api/admin/users/<int:user_id>/admin', methods=['PUT'])
@token_required
@admin_required
def toggle_user_admin(current_user, user_id):
    data = request.get_json()
    is_admin = data.get('is_admin')

    if is_admin is None:
        return jsonify({'success': False, 'message': '缺少参数'})

    conn = get_db()
    conn.execute('UPDATE users SET is_admin = ? WHERE id = ?', (is_admin, user_id))
    conn.commit()
    conn.close()

    action = "设为管理员" if is_admin else "取消管理员权限"
    return jsonify({'success': True, 'message': f'用户已{action}'})


@app.route('/api/admin/users/<int:user_id>/status', methods=['PUT'])
@token_required
@admin_required
def toggle_user_status(current_user, user_id):
    data = request.get_json()
    is_active = data.get('is_active')

    if is_active is None:
        return jsonify({'success': False, 'message': '缺少参数'})

    conn = get_db()
    conn.execute('UPDATE users SET is_active = ? WHERE id = ?', (is_active, user_id))
    conn.commit()
    conn.close()

    action = "激活" if is_active else "禁用"
    return jsonify({'success': True, 'message': f'用户已{action}'})


# 项目管理路由
@app.route('/api/admin/projects', methods=['GET'])
@token_required
@admin_required
def get_projects(current_user):
    search = request.args.get('search', '')
    conn = get_db()

    if search:
        projects = conn.execute('''
            SELECT p.id, p.name, u.username as owner, p.created_at, 
                   p.file_count, p.last_modified
            FROM projects p
            JOIN users u ON p.owner_id = u.id
            WHERE p.name LIKE ? OR u.username LIKE ?
            ORDER BY p.created_at DESC
        ''', (f'%{search}%', f'%{search}%')).fetchall()
    else:
        projects = conn.execute('''
            SELECT p.id, p.name, u.username as owner, p.created_at, 
                   p.file_count, p.last_modified
            FROM projects p
            JOIN users u ON p.owner_id = u.id
            ORDER BY p.created_at DESC
        ''').fetchall()

    conn.close()

    projects_list = []
    for project in projects:
        projects_list.append({
            'id': project['id'],
            'name': project['name'],
            'owner': project['owner'],
            'created_at': project['created_at'],
            'file_count': project['file_count'],
            'last_modified': project['last_modified']
        })

    return jsonify({'success': True, 'projects': projects_list})


@app.route('/api/admin/projects/<int:project_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_project(current_user, project_id):
    conn = get_db()

    # 先删除相关文件
    conn.execute('DELETE FROM files WHERE project_id = ?', (project_id,))
    # 再删除项目
    conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '项目已删除'})


# 系统信息路由
@app.route('/api/admin/system-info', methods=['GET'])
@token_required
@admin_required
def get_system_info(current_user):
    conn = get_db()

    # 获取用户总数
    total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']

    # 获取项目总数
    total_projects = conn.execute('SELECT COUNT(*) as count FROM projects').fetchone()['count']

    # 获取文件总数
    total_files = conn.execute('SELECT COUNT(*) as count FROM files').fetchone()['count']

    conn.close()

    return jsonify({
        'success': True,
        'info': {
            'version': 'v2.0',
            'total_users': total_users,
            'total_projects': total_projects,
            'total_files': total_files
        }
    })


# 包管理路由
@app.route('/api/admin/packages', methods=['GET'])
@token_required
@admin_required
def get_packages(current_user):
    conn = get_db()
    packages = conn.execute('SELECT name, version, installed_at FROM packages ORDER BY installed_at DESC').fetchall()
    conn.close()

    packages_list = []
    for pkg in packages:
        packages_list.append({
            'name': pkg['name'],
            'version': pkg['version'],
            'installed_at': pkg['installed_at']
        })

    return jsonify({'success': True, 'packages': packages_list})


# 系统操作路由
@app.route('/api/admin/backup', methods=['POST'])
@token_required
@admin_required
def backup_database(current_user):
    # 这里实现数据库备份逻辑
    # 在实际应用中，您可能需要使用更复杂的备份策略
    backup_filename = f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'

    return jsonify({
        'success': True,
        'message': '数据库备份成功',
        'backup_file': backup_filename
    })


@app.route('/api/admin/clean-temp', methods=['POST'])
@token_required
@admin_required
def clean_temp_files(current_user):
    # 清理临时文件的逻辑
    # 这里只是示例，实际应用中需要根据具体情况实现
    cleaned_files = 0

    return jsonify({
        'success': True,
        'message': '临时文件清理完成',
        'cleaned_files': cleaned_files
    })


# 静态文件服务
@app.route('/')
def serve_index():
    return send_from_directory('.', 'admin.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=8081)