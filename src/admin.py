from flask import Blueprint, jsonify, request
'''

from src.models.user import User, CodeSubmission, db
'''
from src.user import User, CodeSubmission, db
import jwt
from datetime import datetime, timedelta
from functools import wraps

admin_bp = Blueprint('admin', __name__)

# JWT密钥，应该与user.py中的保持一致
JWT_SECRET = 'your-secret-key-here'

def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            
            if not current_user:
                return jsonify({'message': 'Invalid token!'}), 401
                
            if not current_user.is_admin:
                return jsonify({'message': 'Admin privileges required!'}), 403
                
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_all_users(current_admin):
    """获取所有用户列表"""
    try:
        users = User.query.all()
        users_data = []
        
        for user in users:
            user_info = user.to_dict(include_admin_info=True)
            users_data.append(user_info)
            
        return jsonify({
            'success': True,
            'users': users_data,
            'total_count': len(users_data)
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取用户列表失败: {str(e)}'}), 500

@admin_bp.route('/users', methods=['POST'])
@admin_required
def create_user(current_admin):
    """创建新用户"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        is_admin = data.get('is_admin', False)
        
        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        
        # 检查用户是否已存在
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'message': '用户名已存在'}), 400
        
        # 创建新用户
        user = User(username=username, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '用户创建成功',
            'user': user.to_dict(include_admin_info=True)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'创建用户失败: {str(e)}'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(current_admin, user_id):
    """更新用户信息"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.json
        
        # 防止管理员删除自己的管理员权限
        if user.id == current_admin.id and 'is_admin' in data and not data['is_admin']:
            return jsonify({'success': False, 'message': '不能取消自己的管理员权限'}), 400
        
        # 更新用户信息
        if 'username' in data:
            # 检查用户名是否已被其他用户使用
            existing_user = User.query.filter_by(username=data['username']).first()
            if existing_user and existing_user.id != user.id:
                return jsonify({'success': False, 'message': '用户名已被使用'}), 400
            user.username = data['username']
            
        if 'password' in data and data['password']:
            user.set_password(data['password'])
            
        if 'is_admin' in data:
            user.is_admin = data['is_admin']
            
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '用户信息更新成功',
            'user': user.to_dict(include_admin_info=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新用户失败: {str(e)}'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(current_admin, user_id):
    """删除用户"""
    try:
        user = User.query.get_or_404(user_id)
        
        # 防止管理员删除自己
        if user.id == current_admin.id:
            return jsonify({'success': False, 'message': '不能删除自己的账号'}), 400
        
        username = user.username
        
        # 删除用户的所有代码提交记录
        CodeSubmission.query.filter_by(user_id=user_id).delete()
        
        # 删除用户
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'用户 {username} 已被删除'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除用户失败: {str(e)}'}), 500

@admin_bp.route('/submissions', methods=['GET'])
@admin_required
def get_all_submissions(current_admin):
    """获取所有代码提交记录"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        user_id = request.args.get('user_id', type=int)
        
        query = CodeSubmission.query
        
        # 如果指定了用户ID，则只获取该用户的提交
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        # 按时间倒序排列
        query = query.order_by(CodeSubmission.submission_timestamp.desc())
        
        # 分页
        submissions = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        submissions_data = []
        for submission in submissions.items:
            submission_info = submission.to_dict()
            # 添加用户名信息
            user = User.query.get(submission.user_id)
            submission_info['username'] = user.username if user else 'Unknown'
            submissions_data.append(submission_info)
        
        return jsonify({
            'success': True,
            'submissions': submissions_data,
            'pagination': {
                'page': submissions.page,
                'pages': submissions.pages,
                'per_page': submissions.per_page,
                'total': submissions.total,
                'has_next': submissions.has_next,
                'has_prev': submissions.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取提交记录失败: {str(e)}'}), 500

@admin_bp.route('/submissions/<int:submission_id>', methods=['GET'])
@admin_required
def get_submission_detail(current_admin, submission_id):
    """获取代码提交详情"""
    try:
        submission = CodeSubmission.query.get_or_404(submission_id)
        user = User.query.get(submission.user_id)
        
        submission_info = submission.to_dict()
        submission_info['username'] = user.username if user else 'Unknown'
        
        return jsonify({
            'success': True,
            'submission': submission_info
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取提交详情失败: {str(e)}'}), 500

@admin_bp.route('/submissions/<int:submission_id>', methods=['DELETE'])
@admin_required
def delete_submission(current_admin, submission_id):
    """删除代码提交记录"""
    try:
        submission = CodeSubmission.query.get_or_404(submission_id)
        
        db.session.delete(submission)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '提交记录已删除'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除提交记录失败: {str(e)}'}), 500

@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_system_stats(current_admin):
    """获取系统统计信息"""
    try:
        # 用户统计
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        admin_users = User.query.filter_by(is_admin=True).count()
        
        # 提交统计
        total_submissions = CodeSubmission.query.count()
        today = datetime.utcnow().date()
        today_submissions = CodeSubmission.query.filter(
            CodeSubmission.submission_timestamp >= today
        ).count()
        
        # 最近活跃用户
        recent_users = User.query.filter(
            User.last_login.isnot(None)
        ).order_by(User.last_login.desc()).limit(5).all()
        
        recent_users_data = [user.to_dict(include_admin_info=True) for user in recent_users]
        
        return jsonify({
            'success': True,
            'stats': {
                'users': {
                    'total': total_users,
                    'active': active_users,
                    'admin': admin_users
                },
                'submissions': {
                    'total': total_submissions,
                    'today': today_submissions
                },
                'recent_users': recent_users_data
            }
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取统计信息失败: {str(e)}'}), 500

@admin_bp.route('/make-admin/<int:user_id>', methods=['POST'])
@admin_required
def make_user_admin(current_admin, user_id):
    """设置用户为管理员"""
    try:
        user = User.query.get_or_404(user_id)
        user.make_admin()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'用户 {user.username} 已设置为管理员'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'设置管理员失败: {str(e)}'}), 500

@admin_bp.route('/remove-admin/<int:user_id>', methods=['POST'])
@admin_required
def remove_user_admin(current_admin, user_id):
    """取消用户管理员权限"""
    try:
        user = User.query.get_or_404(user_id)
        
        # 防止取消自己的管理员权限
        if user.id == current_admin.id:
            return jsonify({'success': False, 'message': '不能取消自己的管理员权限'}), 400
        
        user.remove_admin()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'用户 {user.username} 的管理员权限已取消'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'取消管理员权限失败: {str(e)}'}), 500

