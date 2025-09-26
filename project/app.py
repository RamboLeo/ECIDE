from flask import Flask, request, jsonify, render_template, send_file, session, redirect, url_for
from flask_cors import CORS
import os
import json
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 简单的用户数据存储（实际应用中应使用数据库）
users = {
    'admin': {'password': 'admin123', 'role': 'admin'},
    'user1': {'password': 'password1', 'role': 'user'}
}

# 存储提交记录（实际应用中应使用数据库）
submissions = []

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'py', 'txt', 'js', 'html', 'css', 'java', 'c', 'cpp', 'json'}


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('admin'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in users and users[username]['password'] == password:
            session['username'] = username
            session['role'] = users[username]['role']
            return jsonify({'success': True, 'message': '登录成功'})
        else:
            return jsonify({'success': False, 'message': '用户名或密码错误'})

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/admin')
def admin():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('admin.html', username=session['username'])


@app.route('/api/submit', methods=['POST'])
def submit_code():
    if 'username' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    # 检查是否有文件上传
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有文件上传'})

    file = request.files['file']
    project_name = request.form.get('project_name', '未命名项目')

    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'})

    if file and allowed_file(file.filename):
        # 生成唯一文件名
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        # 记录提交信息
        submission = {
            'id': len(submissions) + 1,
            'username': session['username'],
            'project_name': project_name,
            'filename': filename,
            'file_path': file_path,
            'submission_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'file_size': os.path.getsize(file_path)
        }

        submissions.append(submission)

        return jsonify({
            'success': True,
            'message': '文件提交成功',
            'submission': submission
        })

    return jsonify({'success': False, 'message': '不支持的文件类型'})


@app.route('/api/submissions')
def get_submissions():
    if 'username' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    # 如果是管理员，返回所有提交；否则只返回当前用户的提交
    if session.get('role') == 'admin':
        return jsonify({'success': True, 'submissions': submissions})
    else:
        user_submissions = [s for s in submissions if s['username'] == session['username']]
        return jsonify({'success': True, 'submissions': user_submissions})


@app.route('/api/code/<int:submission_id>')
def get_code(submission_id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    # 查找提交记录
    submission = next((s for s in submissions if s['id'] == submission_id), None)

    if not submission:
        return jsonify({'success': False, 'message': '提交记录不存在'})

    # 检查权限（管理员或提交者本人）
    if session.get('role') != 'admin' and submission['username'] != session['username']:
        return jsonify({'success': False, 'message': '没有权限查看此文件'})

    # 读取文件内容
    try:
        with open(submission['file_path'], 'r', encoding='utf-8') as f:
            content = f.read()

        return jsonify({
            'success': True,
            'content': content,
            'submission': submission
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取文件失败: {str(e)}'})


@app.route('/api/save', methods=['POST'])
def save_code():
    if 'username' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    data = request.json
    submission_id = data.get('submission_id')
    content = data.get('content')

    if not submission_id or not content:
        return jsonify({'success': False, 'message': '参数不完整'})

    # 查找提交记录
    submission = next((s for s in submissions if s['id'] == submission_id), None)

    if not submission:
        return jsonify({'success': False, 'message': '提交记录不存在'})

    # 检查权限（管理员或提交者本人）
    if session.get('role') != 'admin' and submission['username'] != session['username']:
        return jsonify({'success': False, 'message': '没有权限修改此文件'})

    # 保存文件内容
    try:
        with open(submission['file_path'], 'w', encoding='utf-8') as f:
            f.write(content)

        return jsonify({'success': True, 'message': '文件保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存文件失败: {str(e)}'})


@app.route('/api/download/<int:submission_id>')
def download_code(submission_id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    # 查找提交记录
    submission = next((s for s in submissions if s['id'] == submission_id), None)

    if not submission:
        return jsonify({'success': False, 'message': '提交记录不存在'})

    # 检查权限（管理员或提交者本人）
    if session.get('role') != 'admin' and submission['username'] != session['username']:
        return jsonify({'success': False, 'message': '没有权限下载此文件'})

    # 返回文件下载
    return send_file(
        submission['file_path'],
        as_attachment=True,
        download_name=submission['filename']
    )


@app.route('/editor/<int:submission_id>')
def code_editor(submission_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    # 查找提交记录
    submission = next((s for s in submissions if s['id'] == submission_id), None)

    if not submission:
        return "提交记录不存在", 404

    # 检查权限（管理员或提交者本人）
    if session.get('role') != 'admin' and submission['username'] != session['username']:
        return "没有权限查看此文件", 403

    return render_template('code_editor.html', submission=submission)


if __name__ == '__main__':
    app.run(debug=True, port=5000)