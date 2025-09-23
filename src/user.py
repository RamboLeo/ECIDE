from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # 关联代码提交记录
    code_submissions = db.relationship('CodeSubmission', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def make_admin(self):
        """设置为管理员"""
        self.is_admin = True

    def remove_admin(self):
        """取消管理员权限"""
        self.is_admin = False

    def deactivate(self):
        """停用用户"""
        self.is_active = False

    def activate(self):
        """激活用户"""
        self.is_active = True

    def update_last_login(self):
        """更新最后登录时间"""
        self.last_login = datetime.utcnow()

    def __repr__(self):
        return f'<User {self.username}>'

    def to_dict(self, include_admin_info=False):
        data = {
            'id': self.id,
            'username': self.username,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_admin_info:
            data['is_admin'] = self.is_admin
            data['submission_count'] = len(self.code_submissions)
            
        return data

class CodeSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    code_content = db.Column(db.Text, nullable=False)
    submission_timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CodeSubmission {self.project_name}/{self.file_path}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'project_name': self.project_name,
            'file_path': self.file_path,
            'code_content': self.code_content,
            'submission_timestamp': self.submission_timestamp.isoformat() if self.submission_timestamp else None
        }
