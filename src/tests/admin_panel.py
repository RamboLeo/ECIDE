import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
import json
from datetime import datetime

class AdminPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("Python IDE 管理员面板")
        self.root.geometry("1400x900")
        
        # 服务器配置
        self.server_url = "http://localhost:8081/api"
        self.token = None
        self.current_admin = None
        
        # 创建界面
        self.create_widgets()
        
    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部工具栏
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 登录状态标签
        self.status_label = ttk.Label(toolbar_frame, text="未登录", font=("Arial", 12, "bold"))
        self.status_label.pack(side=tk.LEFT)
        
        # 登录按钮
        self.login_btn = ttk.Button(toolbar_frame, text="管理员登录", command=self.show_login_dialog)
        self.login_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # 刷新按钮
        self.refresh_btn = ttk.Button(toolbar_frame, text="刷新数据", command=self.refresh_all_data, state=tk.DISABLED)
        self.refresh_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # 主要内容区域 - 使用Notebook分页
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建各个标签页
        self.create_dashboard_tab()
        self.create_users_tab()
        self.create_submissions_tab()
        self.create_system_tab()
        
    def create_dashboard_tab(self):
        """创建仪表板标签页"""
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="仪表板")
        
        # 统计信息框架
        stats_frame = ttk.LabelFrame(dashboard_frame, text="系统统计")
        stats_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 统计信息网格
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # 用户统计
        user_stats_frame = ttk.LabelFrame(stats_grid, text="用户统计")
        user_stats_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.total_users_label = ttk.Label(user_stats_frame, text="总用户数: -", font=("Arial", 12))
        self.total_users_label.pack(pady=2)
        
        self.active_users_label = ttk.Label(user_stats_frame, text="活跃用户: -", font=("Arial", 12))
        self.active_users_label.pack(pady=2)
        
        self.admin_users_label = ttk.Label(user_stats_frame, text="管理员: -", font=("Arial", 12))
        self.admin_users_label.pack(pady=2)
        
        # 提交统计
        submission_stats_frame = ttk.LabelFrame(stats_grid, text="提交统计")
        submission_stats_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.total_submissions_label = ttk.Label(submission_stats_frame, text="总提交数: -", font=("Arial", 12))
        self.total_submissions_label.pack(pady=2)
        
        self.today_submissions_label = ttk.Label(submission_stats_frame, text="今日提交: -", font=("Arial", 12))
        self.today_submissions_label.pack(pady=2)
        
        # 配置网格权重
        stats_grid.columnconfigure(0, weight=1)
        stats_grid.columnconfigure(1, weight=1)
        
        # 最近活跃用户
        recent_frame = ttk.LabelFrame(dashboard_frame, text="最近活跃用户")
        recent_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建表格
        columns = ("用户名", "最后登录", "提交数", "状态")
        self.recent_users_tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=8)
        
        for col in columns:
            self.recent_users_tree.heading(col, text=col)
            self.recent_users_tree.column(col, width=150)
        
        # 添加滚动条
        recent_scrollbar = ttk.Scrollbar(recent_frame, orient=tk.VERTICAL, command=self.recent_users_tree.yview)
        self.recent_users_tree.configure(yscrollcommand=recent_scrollbar.set)
        
        self.recent_users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        recent_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
    def create_users_tab(self):
        """创建用户管理标签页"""
        users_frame = ttk.Frame(self.notebook)
        self.notebook.add(users_frame, text="用户管理")
        
        # 工具栏
        users_toolbar = ttk.Frame(users_frame)
        users_toolbar.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(users_toolbar, text="创建用户", command=self.show_create_user_dialog).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(users_toolbar, text="编辑用户", command=self.edit_selected_user).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(users_toolbar, text="删除用户", command=self.delete_selected_user).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(users_toolbar, text="设为管理员", command=self.make_user_admin).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(users_toolbar, text="取消管理员", command=self.remove_user_admin).pack(side=tk.LEFT, padx=(0, 5))
        
        # 用户列表
        users_list_frame = ttk.Frame(users_frame)
        users_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建表格
        columns = ("ID", "用户名", "管理员", "状态", "创建时间", "最后登录", "提交数")
        self.users_tree = ttk.Treeview(users_list_frame, columns=columns, show="headings")
        
        for col in columns:
            self.users_tree.heading(col, text=col)
            if col == "ID":
                self.users_tree.column(col, width=50)
            elif col in ["管理员", "状态"]:
                self.users_tree.column(col, width=80)
            elif col == "提交数":
                self.users_tree.column(col, width=80)
            else:
                self.users_tree.column(col, width=150)
        
        # 添加滚动条
        users_scrollbar_v = ttk.Scrollbar(users_list_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        users_scrollbar_h = ttk.Scrollbar(users_list_frame, orient=tk.HORIZONTAL, command=self.users_tree.xview)
        self.users_tree.configure(yscrollcommand=users_scrollbar_v.set, xscrollcommand=users_scrollbar_h.set)
        
        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        users_scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)
        users_scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)
        
    def create_submissions_tab(self):
        """创建提交管理标签页"""
        submissions_frame = ttk.Frame(self.notebook)
        self.notebook.add(submissions_frame, text="提交管理")
        
        # 工具栏
        submissions_toolbar = ttk.Frame(submissions_frame)
        submissions_toolbar.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(submissions_toolbar, text="查看详情", command=self.view_submission_detail).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(submissions_toolbar, text="删除提交", command=self.delete_selected_submission).pack(side=tk.LEFT, padx=(0, 5))
        
        # 筛选选项
        ttk.Label(submissions_toolbar, text="用户筛选:").pack(side=tk.LEFT, padx=(20, 5))
        self.user_filter_var = tk.StringVar()
        self.user_filter_combo = ttk.Combobox(submissions_toolbar, textvariable=self.user_filter_var, width=15)
        self.user_filter_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.user_filter_combo.bind("<<ComboboxSelected>>", self.filter_submissions)
        
        ttk.Button(submissions_toolbar, text="清除筛选", command=self.clear_submission_filter).pack(side=tk.LEFT, padx=(5, 0))
        
        # 提交列表
        submissions_list_frame = ttk.Frame(submissions_frame)
        submissions_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建表格
        columns = ("ID", "用户名", "项目名", "文件路径", "提交时间")
        self.submissions_tree = ttk.Treeview(submissions_list_frame, columns=columns, show="headings")
        
        for col in columns:
            self.submissions_tree.heading(col, text=col)
            if col == "ID":
                self.submissions_tree.column(col, width=50)
            elif col == "用户名":
                self.submissions_tree.column(col, width=100)
            else:
                self.submissions_tree.column(col, width=200)
        
        # 添加滚动条
        submissions_scrollbar_v = ttk.Scrollbar(submissions_list_frame, orient=tk.VERTICAL, command=self.submissions_tree.yview)
        submissions_scrollbar_h = ttk.Scrollbar(submissions_list_frame, orient=tk.HORIZONTAL, command=self.submissions_tree.xview)
        self.submissions_tree.configure(yscrollcommand=submissions_scrollbar_v.set, xscrollcommand=submissions_scrollbar_h.set)
        
        self.submissions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        submissions_scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)
        submissions_scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)
        
    def create_system_tab(self):
        """创建系统管理标签页"""
        system_frame = ttk.Frame(self.notebook)
        self.notebook.add(system_frame, text="系统管理")
        
        # 系统信息
        info_frame = ttk.LabelFrame(system_frame, text="系统信息")
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        info_text = """
Python IDE 管理员面板 v1.0

功能说明:
• 用户管理: 创建、编辑、删除用户账号
• 权限管理: 设置和取消管理员权限
• 提交监控: 查看和管理用户代码提交
• 系统统计: 实时查看系统使用情况

安全提醒:
• 请定期更改管理员密码
• 谨慎授予管理员权限
• 定期备份用户数据
        """
        
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(padx=10, pady=10)
        
        # 操作按钮
        actions_frame = ttk.LabelFrame(system_frame, text="系统操作")
        actions_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(actions_frame, text="导出用户数据", command=self.export_users_data).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(actions_frame, text="导出提交数据", command=self.export_submissions_data).pack(side=tk.LEFT, padx=10, pady=10)
        
    def show_login_dialog(self):
        """显示管理员登录对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("管理员登录")
        dialog.geometry("350x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 100))
        
        ttk.Label(dialog, text="管理员用户名:").pack(pady=10)
        username_entry = ttk.Entry(dialog, width=30)
        username_entry.pack(pady=5)
        
        ttk.Label(dialog, text="密码:").pack(pady=(10, 0))
        password_entry = ttk.Entry(dialog, width=30, show="*")
        password_entry.pack(pady=5)
        
        def login():
            username = username_entry.get()
            password = password_entry.get()
            
            if not username or not password:
                messagebox.showerror("错误", "用户名和密码不能为空")
                return
                
            try:
                response = requests.post(f"{self.server_url}/login", 
                                       json={"username": username, "password": password})
                data = response.json()
                
                if data.get("success"):
                    user_info = data.get("user", {})
                    if not user_info.get("is_admin"):
                        messagebox.showerror("错误", "该账号没有管理员权限")
                        return
                        
                    self.token = data.get("token")
                    self.current_admin = user_info
                    self.status_label.config(text=f"管理员: {username}")
                    self.login_btn.config(text="退出登录", command=self.logout)
                    self.refresh_btn.config(state=tk.NORMAL)
                    
                    # 启用所有标签页
                    for i in range(self.notebook.index("end")):
                        self.notebook.tab(i, state="normal")
                    
                    messagebox.showinfo("成功", "管理员登录成功!")
                    dialog.destroy()
                    
                    # 加载数据
                    self.refresh_all_data()
                else:
                    messagebox.showerror("错误", data.get("message", "登录失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")
        
        ttk.Button(dialog, text="登录", command=login).pack(pady=20)
        
        # 回车键登录
        dialog.bind('<Return>', lambda e: login())
        username_entry.focus()
        
    def logout(self):
        """退出登录"""
        self.token = None
        self.current_admin = None
        self.status_label.config(text="未登录")
        self.login_btn.config(text="管理员登录", command=self.show_login_dialog)
        self.refresh_btn.config(state=tk.DISABLED)
        
        # 禁用所有标签页除了第一个
        for i in range(1, self.notebook.index("end")):
            self.notebook.tab(i, state="disabled")
        
        # 切换到第一个标签页
        self.notebook.select(0)
        
        messagebox.showinfo("提示", "已退出登录")
        
    def refresh_all_data(self):
        """刷新所有数据"""
        if not self.token:
            return
            
        self.load_system_stats()
        self.load_users_data()
        self.load_submissions_data()
        
    def load_system_stats(self):
        """加载系统统计数据"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(f"{self.server_url}/admin/stats", headers=headers)
            data = response.json()
            
            if data.get("success"):
                stats = data.get("stats", {})
                user_stats = stats.get("users", {})
                submission_stats = stats.get("submissions", {})
                recent_users = stats.get("recent_users", [])
                
                # 更新统计标签
                self.total_users_label.config(text=f"总用户数: {user_stats.get('total', 0)}")
                self.active_users_label.config(text=f"活跃用户: {user_stats.get('active', 0)}")
                self.admin_users_label.config(text=f"管理员: {user_stats.get('admin', 0)}")
                self.total_submissions_label.config(text=f"总提交数: {submission_stats.get('total', 0)}")
                self.today_submissions_label.config(text=f"今日提交: {submission_stats.get('today', 0)}")
                
                # 更新最近活跃用户列表
                for item in self.recent_users_tree.get_children():
                    self.recent_users_tree.delete(item)
                
                for user in recent_users:
                    last_login = user.get('last_login', '')
                    if last_login:
                        last_login = datetime.fromisoformat(last_login.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                    
                    status = "管理员" if user.get('is_admin') else ("活跃" if user.get('is_active') else "停用")
                    
                    self.recent_users_tree.insert("", "end", values=(
                        user.get('username', ''),
                        last_login,
                        user.get('submission_count', 0),
                        status
                    ))
                    
        except Exception as e:
            messagebox.showerror("错误", f"加载统计数据失败: {str(e)}")
            
    def load_users_data(self):
        """加载用户数据"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(f"{self.server_url}/admin/users", headers=headers)
            data = response.json()
            
            if data.get("success"):
                users = data.get("users", [])
                
                # 清空现有数据
                for item in self.users_tree.get_children():
                    self.users_tree.delete(item)
                
                # 更新用户筛选下拉框
                usernames = ["所有用户"] + [user.get('username', '') for user in users]
                self.user_filter_combo['values'] = usernames
                if not self.user_filter_var.get():
                    self.user_filter_var.set("所有用户")
                
                # 添加用户数据
                for user in users:
                    created_at = user.get('created_at', '')
                    if created_at:
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                    
                    last_login = user.get('last_login', '')
                    if last_login:
                        last_login = datetime.fromisoformat(last_login.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                    else:
                        last_login = "从未登录"
                    
                    self.users_tree.insert("", "end", values=(
                        user.get('id', ''),
                        user.get('username', ''),
                        "是" if user.get('is_admin') else "否",
                        "活跃" if user.get('is_active') else "停用",
                        created_at,
                        last_login,
                        user.get('submission_count', 0)
                    ))
                    
        except Exception as e:
            messagebox.showerror("错误", f"加载用户数据失败: {str(e)}")
            
    def load_submissions_data(self):
        """加载提交数据"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            params = {}
            
            # 应用用户筛选
            if self.user_filter_var.get() and self.user_filter_var.get() != "所有用户":
                # 找到用户ID
                for item in self.users_tree.get_children():
                    values = self.users_tree.item(item)['values']
                    if values[1] == self.user_filter_var.get():  # 用户名匹配
                        params['user_id'] = values[0]  # 用户ID
                        break
            
            response = requests.get(f"{self.server_url}/admin/submissions", headers=headers, params=params)
            data = response.json()
            
            if data.get("success"):
                submissions = data.get("submissions", [])
                
                # 清空现有数据
                for item in self.submissions_tree.get_children():
                    self.submissions_tree.delete(item)
                
                # 添加提交数据
                for submission in submissions:
                    timestamp = submission.get('submission_timestamp', '')
                    if timestamp:
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                    
                    self.submissions_tree.insert("", "end", values=(
                        submission.get('id', ''),
                        submission.get('username', ''),
                        submission.get('project_name', ''),
                        submission.get('file_path', ''),
                        timestamp
                    ))
                    
        except Exception as e:
            messagebox.showerror("错误", f"加载提交数据失败: {str(e)}")
            
    def show_create_user_dialog(self):
        """显示创建用户对话框"""
        if not self.token:
            messagebox.showwarning("警告", "请先登录")
            return
            
        dialog = tk.Toplevel(self.root)
        dialog.title("创建新用户")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 100))
        
        ttk.Label(dialog, text="用户名:").pack(pady=10)
        username_entry = ttk.Entry(dialog, width=30)
        username_entry.pack(pady=5)
        
        ttk.Label(dialog, text="密码:").pack(pady=(10, 0))
        password_entry = ttk.Entry(dialog, width=30, show="*")
        password_entry.pack(pady=5)
        
        ttk.Label(dialog, text="确认密码:").pack(pady=(10, 0))
        confirm_password_entry = ttk.Entry(dialog, width=30, show="*")
        confirm_password_entry.pack(pady=5)
        
        # 管理员权限选择
        is_admin_var = tk.BooleanVar()
        ttk.Checkbutton(dialog, text="设为管理员", variable=is_admin_var).pack(pady=10)
        
        def create_user():
            username = username_entry.get()
            password = password_entry.get()
            confirm_password = confirm_password_entry.get()
            is_admin = is_admin_var.get()
            
            if not username or not password:
                messagebox.showerror("错误", "用户名和密码不能为空")
                return
                
            if password != confirm_password:
                messagebox.showerror("错误", "两次输入的密码不一致")
                return
                
            try:
                headers = {"Authorization": f"Bearer {self.token}"}
                data = {
                    "username": username,
                    "password": password,
                    "is_admin": is_admin
                }
                
                response = requests.post(f"{self.server_url}/admin/users", 
                                       json=data, headers=headers)
                result = response.json()
                
                if result.get("success"):
                    messagebox.showinfo("成功", "用户创建成功!")
                    dialog.destroy()
                    self.load_users_data()
                else:
                    messagebox.showerror("错误", result.get("message", "创建用户失败"))
            except Exception as e:
                messagebox.showerror("错误", f"创建用户失败: {str(e)}")
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="创建", command=create_user).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT)
        
        username_entry.focus()
        
    def edit_selected_user(self):
        """编辑选中的用户"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要编辑的用户")
            return
            
        item = selection[0]
        values = self.users_tree.item(item)['values']
        user_id = values[0]
        current_username = values[1]
        is_admin = values[2] == "是"
        is_active = values[3] == "活跃"
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑用户: {current_username}")
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 100))
        
        ttk.Label(dialog, text="用户名:").pack(pady=10)
        username_entry = ttk.Entry(dialog, width=30)
        username_entry.pack(pady=5)
        username_entry.insert(0, current_username)
        
        ttk.Label(dialog, text="新密码 (留空表示不修改):").pack(pady=(10, 0))
        password_entry = ttk.Entry(dialog, width=30, show="*")
        password_entry.pack(pady=5)
        
        # 权限选择
        is_admin_var = tk.BooleanVar(value=is_admin)
        ttk.Checkbutton(dialog, text="管理员权限", variable=is_admin_var).pack(pady=5)
        
        is_active_var = tk.BooleanVar(value=is_active)
        ttk.Checkbutton(dialog, text="账号激活", variable=is_active_var).pack(pady=5)
        
        def update_user():
            username = username_entry.get()
            password = password_entry.get()
            
            if not username:
                messagebox.showerror("错误", "用户名不能为空")
                return
                
            try:
                headers = {"Authorization": f"Bearer {self.token}"}
                data = {
                    "username": username,
                    "is_admin": is_admin_var.get(),
                    "is_active": is_active_var.get()
                }
                
                if password:
                    data["password"] = password
                
                response = requests.put(f"{self.server_url}/admin/users/{user_id}", 
                                      json=data, headers=headers)
                result = response.json()
                
                if result.get("success"):
                    messagebox.showinfo("成功", "用户信息更新成功!")
                    dialog.destroy()
                    self.load_users_data()
                else:
                    messagebox.showerror("错误", result.get("message", "更新用户失败"))
            except Exception as e:
                messagebox.showerror("错误", f"更新用户失败: {str(e)}")
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="更新", command=update_user).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT)
        
    def delete_selected_user(self):
        """删除选中的用户"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要删除的用户")
            return
            
        item = selection[0]
        values = self.users_tree.item(item)['values']
        user_id = values[0]
        username = values[1]
        
        if not messagebox.askyesno("确认删除", f"确定要删除用户 {username} 吗？\n此操作将同时删除该用户的所有提交记录，且不可恢复！"):
            return
            
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.delete(f"{self.server_url}/admin/users/{user_id}", headers=headers)
            result = response.json()
            
            if result.get("success"):
                messagebox.showinfo("成功", f"用户 {username} 已被删除")
                self.load_users_data()
                self.load_submissions_data()  # 刷新提交数据
            else:
                messagebox.showerror("错误", result.get("message", "删除用户失败"))
        except Exception as e:
            messagebox.showerror("错误", f"删除用户失败: {str(e)}")
            
    def make_user_admin(self):
        """设置用户为管理员"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要设置的用户")
            return
            
        item = selection[0]
        values = self.users_tree.item(item)['values']
        user_id = values[0]
        username = values[1]
        
        if values[2] == "是":
            messagebox.showinfo("提示", f"用户 {username} 已经是管理员")
            return
            
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.post(f"{self.server_url}/admin/make-admin/{user_id}", headers=headers)
            result = response.json()
            
            if result.get("success"):
                messagebox.showinfo("成功", f"用户 {username} 已设置为管理员")
                self.load_users_data()
            else:
                messagebox.showerror("错误", result.get("message", "设置管理员失败"))
        except Exception as e:
            messagebox.showerror("错误", f"设置管理员失败: {str(e)}")
            
    def remove_user_admin(self):
        """取消用户管理员权限"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要取消权限的用户")
            return
            
        item = selection[0]
        values = self.users_tree.item(item)['values']
        user_id = values[0]
        username = values[1]
        
        if values[2] == "否":
            messagebox.showinfo("提示", f"用户 {username} 不是管理员")
            return
            
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.post(f"{self.server_url}/admin/remove-admin/{user_id}", headers=headers)
            result = response.json()
            
            if result.get("success"):
                messagebox.showinfo("成功", f"用户 {username} 的管理员权限已取消")
                self.load_users_data()
            else:
                messagebox.showerror("错误", result.get("message", "取消管理员权限失败"))
        except Exception as e:
            messagebox.showerror("错误", f"取消管理员权限失败: {str(e)}")
            
    def view_submission_detail(self):
        """查看提交详情"""
        selection = self.submissions_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要查看的提交记录")
            return
            
        item = selection[0]
        values = self.submissions_tree.item(item)['values']
        submission_id = values[0]
        
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(f"{self.server_url}/admin/submissions/{submission_id}", headers=headers)
            result = response.json()
            
            if result.get("success"):
                submission = result.get("submission", {})
                
                # 创建详情窗口
                detail_window = tk.Toplevel(self.root)
                detail_window.title(f"提交详情 - ID: {submission_id}")
                detail_window.geometry("800x600")
                detail_window.transient(self.root)
                
                # 基本信息
                info_frame = ttk.LabelFrame(detail_window, text="基本信息")
                info_frame.pack(fill=tk.X, padx=10, pady=10)
                
                info_text = f"""
用户: {submission.get('username', '')}
项目名: {submission.get('project_name', '')}
文件路径: {submission.get('file_path', '')}
提交时间: {submission.get('submission_timestamp', '')}
                """
                ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(padx=10, pady=10)
                
                # 代码内容
                code_frame = ttk.LabelFrame(detail_window, text="代码内容")
                code_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                code_text = scrolledtext.ScrolledText(code_frame, wrap=tk.NONE, font=("Consolas", 10))
                code_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                code_text.insert(tk.END, submission.get('code_content', ''))
                code_text.config(state=tk.DISABLED)
                
            else:
                messagebox.showerror("错误", result.get("message", "获取提交详情失败"))
        except Exception as e:
            messagebox.showerror("错误", f"获取提交详情失败: {str(e)}")
            
    def delete_selected_submission(self):
        """删除选中的提交记录"""
        selection = self.submissions_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要删除的提交记录")
            return
            
        item = selection[0]
        values = self.submissions_tree.item(item)['values']
        submission_id = values[0]
        username = values[1]
        project_name = values[2]
        file_path = values[3]
        
        if not messagebox.askyesno("确认删除", f"确定要删除以下提交记录吗？\n\n用户: {username}\n项目: {project_name}\n文件: {file_path}"):
            return
            
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.delete(f"{self.server_url}/admin/submissions/{submission_id}", headers=headers)
            result = response.json()
            
            if result.get("success"):
                messagebox.showinfo("成功", "提交记录已删除")
                self.load_submissions_data()
            else:
                messagebox.showerror("错误", result.get("message", "删除提交记录失败"))
        except Exception as e:
            messagebox.showerror("错误", f"删除提交记录失败: {str(e)}")
            
    def filter_submissions(self, event=None):
        """筛选提交记录"""
        self.load_submissions_data()
        
    def clear_submission_filter(self):
        """清除提交筛选"""
        self.user_filter_var.set("所有用户")
        self.load_submissions_data()
        
    def export_users_data(self):
        """导出用户数据"""
        messagebox.showinfo("提示", "导出功能开发中...")
        
    def export_submissions_data(self):
        """导出提交数据"""
        messagebox.showinfo("提示", "导出功能开发中...")

if __name__ == "__main__":
    root = tk.Tk()
    app = AdminPanel(root)
    root.mainloop()

