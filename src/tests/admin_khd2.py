import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import requests
import json
import os
import subprocess
import sys
import threading
import queue
from pathlib import Path


class PythonIDEClient:
    def __init__(self, root):
        self.root = root
        self.root.title("EC Python IDE 客户端 v2.0")
        self.root.geometry("1400x900")

        # 服务器配置
        self.server_url = "http://localhost:8081/api"
        self.token = None
        self.admin_token = None  # 新增管理员token
        self.current_user = None
        self.current_admin = None  # 新增当前管理员
        self.current_project_path = None
        self.current_file_path = None

        # 控制台相关
        self.console_process = None
        self.console_queue = queue.Queue()

        # 创建界面
        self.create_widgets()

        # 启动控制台输出监控
        self.start_console_monitor()

    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 顶部工具栏
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 10))

        # 登录状态标签
        self.status_label = ttk.Label(toolbar_frame, text="未登录")
        self.status_label.pack(side=tk.LEFT)

        # 管理员状态标签
        self.admin_status_label = ttk.Label(toolbar_frame, text="管理员: 未登录", foreground="red")
        self.admin_status_label.pack(side=tk.LEFT, padx=(20, 0))

        # 项目路径标签
        self.project_label = ttk.Label(toolbar_frame, text="未选择项目", foreground="blue")
        self.project_label.pack(side=tk.LEFT, padx=(20, 0))

        # 注册按钮
        self.register_btn = ttk.Button(toolbar_frame, text="注册", command=self.show_register_dialog)
        self.register_btn.pack(side=tk.RIGHT)

        # 登录按钮
        self.login_btn = ttk.Button(toolbar_frame, text="登录", command=self.show_login_dialog)
        self.login_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # 管理按钮
        self.admin_login_btn = ttk.Button(toolbar_frame, text="管理登录", command=self.show_admin_login_dialog)
        self.admin_login_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # 主要内容区域 - 使用PanedWindow分割
        main_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        # 左侧面板 - 项目文件树
        left_frame = ttk.LabelFrame(main_paned, text="项目文件", width=300)
        main_paned.add(left_frame, weight=1)

        # 项目操作按钮
        project_btn_frame = ttk.Frame(left_frame)
        project_btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(project_btn_frame, text="导入项目", command=self.import_project).pack(side=tk.LEFT)
        ttk.Button(project_btn_frame, text="新建文件", command=self.new_file).pack(side=tk.LEFT, padx=(5, 0))

        # 文件树
        self.file_tree = ttk.Treeview(left_frame)
        self.file_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.file_tree.bind("<Double-1>", self.on_file_select)

        # 右侧区域 - 使用垂直分割
        right_paned = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
        main_paned.add(right_paned, weight=3)

        # 代码编辑区域
        editor_frame = ttk.Frame(right_paned)
        right_paned.add(editor_frame, weight=2)

        # 编辑器工具栏
        editor_toolbar = ttk.Frame(editor_frame)
        editor_toolbar.pack(fill=tk.X, pady=(0, 5))

        self.file_label = ttk.Label(editor_toolbar, text="未打开文件")
        self.file_label.pack(side=tk.LEFT)

        ttk.Button(editor_toolbar, text="保存", command=self.save_file).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(editor_toolbar, text="运行", command=self.run_code).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(editor_toolbar, text="提交到服务器", command=self.submit_code).pack(side=tk.RIGHT, padx=(5, 0))

        # 代码编辑器
        self.code_editor = scrolledtext.ScrolledText(editor_frame, wrap=tk.NONE, font=("Consolas", 11))
        self.code_editor.pack(fill=tk.BOTH, expand=True)

        # 底部区域 - 使用Notebook分页
        bottom_notebook = ttk.Notebook(right_paned)
        right_paned.add(bottom_notebook, weight=1)

        # 输出页面
        output_frame = ttk.Frame(bottom_notebook)
        bottom_notebook.add(output_frame, text="程序输出")

        self.output_text = scrolledtext.ScrolledText(output_frame, height=8, font=("Consolas", 10))
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 控制台页面
        console_frame = ttk.Frame(bottom_notebook)
        bottom_notebook.add(console_frame, text="控制台")

        # 控制台工具栏
        console_toolbar = ttk.Frame(console_frame)
        console_toolbar.pack(fill=tk.X, padx=5, pady=(5, 0))

        ttk.Button(console_toolbar, text="安装库", command=self.show_install_package_dialog).pack(side=tk.LEFT)
        ttk.Button(console_toolbar, text="列出已安装", command=self.list_packages).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(console_toolbar, text="清空", command=self.clear_console).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(console_toolbar, text="创建虚拟环境", command=self.create_venv).pack(side=tk.LEFT, padx=(5, 0))

        # 控制台输出
        self.console_text = scrolledtext.ScrolledText(console_frame, height=8, font=("Consolas", 10),
                                                      background="black", foreground="green")
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 控制台输入
        console_input_frame = ttk.Frame(console_frame)
        console_input_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ttk.Label(console_input_frame, text="$").pack(side=tk.LEFT)
        self.console_input = ttk.Entry(console_input_frame, font=("Consolas", 10))
        self.console_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.console_input.bind("<Return>", self.execute_console_command)

        ttk.Button(console_input_frame, text="执行", command=lambda: self.execute_console_command(None)).pack(
            side=tk.RIGHT, padx=(5, 0))

        # 包管理页面
        package_frame = ttk.Frame(bottom_notebook)
        bottom_notebook.add(package_frame, text="包管理")

        # 包管理工具栏
        package_toolbar = ttk.Frame(package_frame)
        package_toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(package_toolbar, text="搜索包:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(package_toolbar, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.search_entry.bind("<Return>", self.search_packages)

        ttk.Button(package_toolbar, text="搜索", command=lambda: self.search_packages(None)).pack(side=tk.LEFT,
                                                                                                  padx=(5, 0))
        ttk.Button(package_toolbar, text="刷新已安装", command=self.refresh_installed_packages).pack(side=tk.LEFT,
                                                                                                     padx=(5, 0))

        # 包列表
        package_list_frame = ttk.Frame(package_frame)
        package_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 已安装包列表
        installed_frame = ttk.LabelFrame(package_list_frame, text="已安装的包")
        installed_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.installed_listbox = tk.Listbox(installed_frame, font=("Consolas", 9))
        self.installed_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.installed_listbox.bind("<Double-1>", self.uninstall_selected_package)

        # 搜索结果列表
        search_frame = ttk.LabelFrame(package_list_frame, text="搜索结果")
        search_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.search_listbox = tk.Listbox(search_frame, font=("Consolas", 9))
        self.search_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.search_listbox.bind("<Double-1>", self.install_selected_package)

        # 初始化控制台
        self.console_text.insert(tk.END, "Python IDE 控制台 v2.0\n")
        self.console_text.insert(tk.END, "=" * 50 + "\n")
        self.console_text.insert(tk.END, "提示: 双击已安装包可卸载，双击搜索结果可安装\n\n")

        # 加载已安装包
        self.refresh_installed_packages()

    def create_admin_panel(self):
        """创建后台管理面板"""
        if not hasattr(self, 'admin_notebook'):
            self.admin_notebook = ttk.Notebook(self.root)
            self.admin_notebook.pack(fill=tk.BOTH, expand=True)

        # 用户管理标签页
        self.create_users_tab()

        # 项目管理标签页
        self.create_projects_tab()

        # 系统设置标签页
        self.create_settings_tab()

    def create_users_tab(self):
        """创建用户管理标签页"""
        users_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(users_frame, text="用户管理")

        # 工具栏
        users_toolbar = ttk.Frame(users_frame)
        users_toolbar.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(users_toolbar, text="刷新列表", command=self.refresh_users_list).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(users_toolbar, text="创建用户", command=self.show_create_user_dialog).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(users_toolbar, text="编辑用户", command=self.edit_selected_user).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(users_toolbar, text="删除用户", command=self.delete_selected_user).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(users_toolbar, text="设为管理员", command=self.make_user_admin).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(users_toolbar, text="取消管理员", command=self.remove_user_admin).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(users_toolbar, text="激活/禁用", command=self.toggle_user_status).pack(side=tk.LEFT, padx=(0, 5))

        # 搜索框
        search_frame = ttk.Frame(users_frame)
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.user_search_entry = ttk.Entry(search_frame, width=30)
        self.user_search_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.user_search_entry.bind("<Return>", lambda e: self.refresh_users_list())

        ttk.Button(search_frame, text="搜索", command=lambda: self.refresh_users_list()).pack(side=tk.LEFT, padx=(5, 0))

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

        scrollbar = ttk.Scrollbar(users_list_frame, orient="vertical", command=self.users_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.users_tree.configure(yscrollcommand=scrollbar.set)
        self.users_tree.pack(fill=tk.BOTH, expand=True)

        # 初始加载用户列表
        self.refresh_users_list()

    def refresh_users_list(self):
        """从服务器获取用户列表并刷新显示"""
        if not self.admin_token:
            messagebox.showwarning("警告", "需要管理员权限")
            return

        try:
            search_term = self.user_search_entry.get().strip()
            params = {}
            if search_term:
                params['search'] = search_term

            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = requests.get(f"{self.server_url}/admin/users", headers=headers, params=params)
            data = response.json()

            if data.get("success"):
                # 清空现有列表
                for item in self.users_tree.get_children():
                    self.users_tree.delete(item)

                # 添加新数据
                for user in data.get("users", []):
                    self.users_tree.insert("", tk.END, values=(
                        user.get("id"),
                        user.get("username"),
                        "是" if user.get("is_admin") else "否",
                        "活跃" if user.get("is_active") else "禁用",
                        user.get("created_at"),
                        user.get("last_login"),
                        user.get("submission_count", 0)
                    ))
            else:
                messagebox.showerror("错误", data.get("message", "获取用户列表失败"))
        except Exception as e:
            messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

    def show_create_user_dialog(self):
        """显示创建用户对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("创建新用户")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="用户名:").pack(pady=10)
        username_entry = ttk.Entry(dialog, width=30)
        username_entry.pack(pady=5)

        ttk.Label(dialog, text="密码:").pack(pady=(10, 0))
        password_entry = ttk.Entry(dialog, width=30, show="*")
        password_entry.pack(pady=5)

        ttk.Label(dialog, text="确认密码:").pack(pady=(10, 0))
        confirm_password_entry = ttk.Entry(dialog, width=30, show="*")
        confirm_password_entry.pack(pady=5)

        is_admin_var = tk.BooleanVar()
        ttk.Checkbutton(dialog, text="设为管理员", variable=is_admin_var).pack(pady=10)

        def create_user():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            confirm_password = confirm_password_entry.get().strip()
            is_admin = is_admin_var.get()

            if not username or not password:
                messagebox.showerror("错误", "用户名和密码不能为空")
                return

            if password != confirm_password:
                messagebox.showerror("错误", "两次输入的密码不一致")
                return

            try:
                headers = {"Authorization": f"Bearer {self.admin_token}"}
                response = requests.post(
                    f"{self.server_url}/admin/users",
                    json={
                        "username": username,
                        "password": password,
                        "is_admin": is_admin
                    },
                    headers=headers
                )
                data = response.json()

                if data.get("success"):
                    messagebox.showinfo("成功", "用户创建成功")
                    dialog.destroy()
                    self.refresh_users_list()
                else:
                    messagebox.showerror("错误", data.get("message", "创建用户失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="创建", command=create_user).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT)

        username_entry.focus()

    def edit_selected_user(self):
        """编辑选中的用户"""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return

        user_id = self.users_tree.item(selected[0], "values")[0]
        username = self.users_tree.item(selected[0], "values")[1]
        is_admin = self.users_tree.item(selected[0], "values")[2] == "是"

        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑用户: {username}")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"用户名: {username}").pack(pady=10)

        ttk.Label(dialog, text="新密码 (留空不修改):").pack(pady=(10, 0))
        password_entry = ttk.Entry(dialog, width=30, show="*")
        password_entry.pack(pady=5)

        ttk.Label(dialog, text="确认新密码:").pack(pady=(10, 0))
        confirm_password_entry = ttk.Entry(dialog, width=30, show="*")
        confirm_password_entry.pack(pady=5)

        is_admin_var = tk.BooleanVar(value=is_admin)
        ttk.Checkbutton(dialog, text="管理员", variable=is_admin_var).pack(pady=10)

        def update_user():
            password = password_entry.get().strip()
            confirm_password = confirm_password_entry.get().strip()
            new_is_admin = is_admin_var.get()

            if password and password != confirm_password:
                messagebox.showerror("错误", "两次输入的密码不一致")
                return

            try:
                update_data = {"is_admin": new_is_admin}
                if password:
                    update_data["password"] = password

                headers = {"Authorization": f"Bearer {self.admin_token}"}
                response = requests.put(
                    f"{self.server_url}/admin/users/{user_id}",
                    json=update_data,
                    headers=headers
                )
                data = response.json()

                if data.get("success"):
                    messagebox.showinfo("成功", "用户信息已更新")
                    dialog.destroy()
                    self.refresh_users_list()
                else:
                    messagebox.showerror("错误", data.get("message", "更新用户失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="更新", command=update_user).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT)

    def delete_selected_user(self):
        """删除选中的用户"""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return

        user_id = self.users_tree.item(selected[0], "values")[0]
        username = self.users_tree.item(selected[0], "values")[1]

        if messagebox.askyesno("确认删除", f"确定要删除用户 {username} 吗？此操作不可恢复！"):
            try:
                headers = {"Authorization": f"Bearer {self.admin_token}"}
                response = requests.delete(
                    f"{self.server_url}/admin/users/{user_id}",
                    headers=headers
                )
                data = response.json()

                if data.get("success"):
                    messagebox.showinfo("成功", "用户已删除")
                    self.refresh_users_list()
                else:
                    messagebox.showerror("错误", data.get("message", "删除用户失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

    def make_user_admin(self):
        """将选中的用户设为管理员"""
        self.change_user_admin_status(True)

    def remove_user_admin(self):
        """取消选中用户的管理员权限"""
        self.change_user_admin_status(False)

    def change_user_admin_status(self, make_admin):
        """修改用户管理员状态"""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return

        user_id = self.users_tree.item(selected[0], "values")[0]
        username = self.users_tree.item(selected[0], "values")[1]
        current_status = self.users_tree.item(selected[0], "values")[2] == "是"

        if make_admin and current_status:
            messagebox.showinfo("提示", "该用户已经是管理员")
            return
        elif not make_admin and not current_status:
            messagebox.showinfo("提示", "该用户不是管理员")
            return

        action = "设为管理员" if make_admin else "取消管理员权限"
        if messagebox.askyesno("确认", f"确定要将用户 {username} {action} 吗？"):
            try:
                headers = {"Authorization": f"Bearer {self.admin_token}"}
                response = requests.put(
                    f"{self.server_url}/admin/users/{user_id}/admin",
                    json={"is_admin": make_admin},
                    headers=headers
                )
                data = response.json()

                if data.get("success"):
                    messagebox.showinfo("成功", f"用户 {username} 已{action}")
                    self.refresh_users_list()
                else:
                    messagebox.showerror("错误", data.get("message", "操作失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

    def toggle_user_status(self):
        """切换用户激活状态"""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return

        user_id = self.users_tree.item(selected[0], "values")[0]
        username = self.users_tree.item(selected[0], "values")[1]
        current_status = self.users_tree.item(selected[0], "values")[3] == "活跃"
        new_status = not current_status

        action = "激活" if new_status else "禁用"
        if messagebox.askyesno("确认", f"确定要{action}用户 {username} 吗？"):
            try:
                headers = {"Authorization": f"Bearer {self.admin_token}"}
                response = requests.put(
                    f"{self.server_url}/admin/users/{user_id}/status",
                    json={"is_active": new_status},
                    headers=headers
                )
                data = response.json()

                if data.get("success"):
                    messagebox.showinfo("成功", f"用户 {username} 已{action}")
                    self.refresh_users_list()
                else:
                    messagebox.showerror("错误", data.get("message", "操作失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

    def create_projects_tab(self):
        """创建项目管理标签页"""
        projects_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(projects_frame, text="项目管理")

        # 工具栏
        projects_toolbar = ttk.Frame(projects_frame)
        projects_toolbar.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(projects_toolbar, text="刷新列表", command=self.refresh_projects_list).pack(side=tk.LEFT,
                                                                                               padx=(0, 5))
        ttk.Button(projects_toolbar, text="删除项目", command=self.delete_selected_project).pack(side=tk.LEFT,
                                                                                                 padx=(0, 5))

        # 搜索框
        search_frame = ttk.Frame(projects_frame)
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.project_search_entry = ttk.Entry(search_frame, width=30)
        self.project_search_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.project_search_entry.bind("<Return>", lambda e: self.refresh_projects_list())

        ttk.Button(search_frame, text="搜索", command=lambda: self.refresh_projects_list()).pack(side=tk.LEFT,
                                                                                                 padx=(5, 0))

        # 项目列表
        projects_list_frame = ttk.Frame(projects_frame)
        projects_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 创建表格
        columns = ("ID", "项目名", "所有者", "创建时间", "文件数", "最后修改")
        self.projects_tree = ttk.Treeview(projects_list_frame, columns=columns, show="headings")

        for col in columns:
            self.projects_tree.heading(col, text=col)
            if col == "ID":
                self.projects_tree.column(col, width=50)
            elif col in ["文件数"]:
                self.projects_tree.column(col, width=80)
            else:
                self.projects_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(projects_list_frame, orient="vertical", command=self.projects_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.projects_tree.configure(yscrollcommand=scrollbar.set)
        self.projects_tree.pack(fill=tk.BOTH, expand=True)

        # 初始加载项目列表
        self.refresh_projects_list()

    def refresh_projects_list(self):
        """从服务器获取项目列表并刷新显示"""
        if not self.admin_token:
            messagebox.showwarning("警告", "需要管理员权限")
            return

        try:
            search_term = self.project_search_entry.get().strip()
            params = {}
            if search_term:
                params['search'] = search_term

            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = requests.get(f"{self.server_url}/admin/projects", headers=headers, params=params)
            data = response.json()

            if data.get("success"):
                # 清空现有列表
                for item in self.projects_tree.get_children():
                    self.projects_tree.delete(item)

                # 添加新数据
                for project in data.get("projects", []):
                    self.projects_tree.insert("", tk.END, values=(
                        project.get("id"),
                        project.get("name"),
                        project.get("owner"),
                        project.get("created_at"),
                        project.get("file_count", 0),
                        project.get("last_modified")
                    ))
            else:
                messagebox.showerror("错误", data.get("message", "获取项目列表失败"))
        except Exception as e:
            messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

    def delete_selected_project(self):
        """删除选中的项目"""
        selected = self.projects_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个项目")
            return

        project_id = self.projects_tree.item(selected[0], "values")[0]
        project_name = self.projects_tree.item(selected[0], "values")[1]

        if messagebox.askyesno("确认删除", f"确定要删除项目 {project_name} 吗？此操作不可恢复！"):
            try:
                headers = {"Authorization": f"Bearer {self.admin_token}"}
                response = requests.delete(
                    f"{self.server_url}/admin/projects/{project_id}",
                    headers=headers
                )
                data = response.json()

                if data.get("success"):
                    messagebox.showinfo("成功", "项目已删除")
                    self.refresh_projects_list()
                else:
                    messagebox.showerror("错误", data.get("message", "删除项目失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

    def create_settings_tab(self):
        """创建系统设置标签页"""
        settings_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(settings_frame, text="系统设置")

        # 系统信息
        info_frame = ttk.LabelFrame(settings_frame, text="系统信息")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text="服务器版本:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.server_version_label = ttk.Label(info_frame, text="未知")
        self.server_version_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(info_frame, text="用户总数:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.total_users_label = ttk.Label(info_frame, text="0")
        self.total_users_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(info_frame, text="项目总数:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.total_projects_label = ttk.Label(info_frame, text="0")
        self.total_projects_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(info_frame, text="文件总数:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.total_files_label = ttk.Label(info_frame, text="0")
        self.total_files_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        # 系统操作
        actions_frame = ttk.LabelFrame(settings_frame, text="系统操作")
        actions_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(actions_frame, text="刷新系统信息", command=self.refresh_system_info).pack(pady=5)
        ttk.Button(actions_frame, text="备份数据库", command=self.backup_database).pack(pady=5)
        ttk.Button(actions_frame, text="清理临时文件", command=self.clean_temp_files).pack(pady=5)

        # 初始加载系统信息
        self.refresh_system_info()

    def refresh_system_info(self):
        """刷新系统信息"""
        if not self.admin_token:
            return

        try:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = requests.get(f"{self.server_url}/admin/system-info", headers=headers)
            data = response.json()

            if data.get("success"):
                info = data.get("info", {})
                self.server_version_label.config(text=info.get("version", "未知"))
                self.total_users_label.config(text=str(info.get("total_users", 0)))
                self.total_projects_label.config(text=str(info.get("total_projects", 0)))
                self.total_files_label.config(text=str(info.get("total_files", 0)))
            else:
                messagebox.showerror("错误", data.get("message", "获取系统信息失败"))
        except Exception as e:
            messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

    def backup_database(self):
        """备份数据库"""
        if not self.admin_token:
            return

        if messagebox.askyesno("确认", "确定要备份数据库吗？"):
            try:
                headers = {"Authorization": f"Bearer {self.admin_token}"}
                response = requests.post(f"{self.server_url}/admin/backup", headers=headers)
                data = response.json()

                if data.get("success"):
                    messagebox.showinfo("成功", "数据库备份成功")
                else:
                    messagebox.showerror("错误", data.get("message", "备份失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

    def clean_temp_files(self):
        """清理临时文件"""
        if not self.admin_token:
            return

        if messagebox.askyesno("确认", "确定要清理临时文件吗？"):
            try:
                headers = {"Authorization": f"Bearer {self.admin_token}"}
                response = requests.post(f"{self.server_url}/admin/clean-temp", headers=headers)
                data = response.json()

                if data.get("success"):
                    messagebox.showinfo("成功", f"已清理 {data.get('cleaned_files', 0)} 个临时文件")
                else:
                    messagebox.showerror("错误", data.get("message", "清理失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

    def show_login_dialog(self, is_admin=False):
        """显示登录对话框，is_admin表示是否是管理员登录"""
        dialog = tk.Toplevel(self.root)
        dialog.title("管理员登录" if is_admin else "用户登录")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 500, self.root.winfo_rooty() + 200))

        ttk.Label(dialog, text="用户名:").pack(pady=10)
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

                    if is_admin and not user_info.get("is_admin"):
                        messagebox.showerror("错误", "该账号没有管理员权限")
                        return

                    # 根据登录类型设置不同的token和用户信息
                    if is_admin:
                        self.admin_token = data.get("token")
                        self.current_admin = user_info
                        self.admin_status_label.config(text=f"管理员: {username}", foreground="green")
                        self.admin_login_btn.config(text="退出管理", command=self.admin_logout)
                        # 创建管理面板
                        self.create_admin_panel()
                    else:
                        self.token = data.get("token")
                        self.current_user = user_info
                        self.status_label.config(text=f"已登录: {username}")
                        self.login_btn.config(text="退出登录", command=self.user_logout)

                    messagebox.showinfo("成功", "登录成功!")
                    dialog.destroy()
                else:
                    messagebox.showerror("错误", data.get("message", "登录失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

        ttk.Button(dialog, text="登录", command=login).pack(pady=20)

        # 回车键登录
        dialog.bind('<Return>', lambda e: login())
        username_entry.focus()

    def show_admin_login_dialog(self):
        """显示管理员登录对话框"""
        # 如果当前用户已经是管理员，直接显示管理界面
        if self.current_admin:
            self.create_admin_panel()
            return

        self.show_login_dialog(is_admin=True)

    def user_logout(self):
        """普通用户退出登录"""
        self.token = None
        self.current_user = None
        self.status_label.config(text="未登录")
        self.login_btn.config(text="登录", command=self.show_login_dialog)
        messagebox.showinfo("提示", "已退出登录")

    def admin_logout(self):
        """管理员退出登录"""
        if hasattr(self, 'admin_notebook'):
            self.admin_notebook.destroy()
            del self.admin_notebook

        self.admin_token = None
        self.current_admin = None
        self.admin_status_label.config(text="管理员: 未登录", foreground="red")
        self.admin_login_btn.config(text="管理登录", command=self.show_admin_login_dialog)
        messagebox.showinfo("提示", "已退出管理员登录")

    def show_register_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("用户注册")
        dialog.geometry("300x300")
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 500, self.root.winfo_rooty() + 200))

        ttk.Label(dialog, text="用户名:").pack(pady=20)
        username_entry = ttk.Entry(dialog, width=30)
        username_entry.pack(pady=5)

        ttk.Label(dialog, text="密码:").pack(pady=(20, 0))
        password_entry = ttk.Entry(dialog, width=30, show="*")
        password_entry.pack(pady=5)

        ttk.Label(dialog, text="确认密码:").pack(pady=(20, 0))
        confirm_password_entry = ttk.Entry(dialog, width=30, show="*")
        confirm_password_entry.pack(pady=5)

        def register():
            username = username_entry.get()
            password = password_entry.get()
            confirm_password = confirm_password_entry.get()

            if not username or not password:
                messagebox.showerror("错误", "用户名和密码不能为空")
                return

            if password != confirm_password:
                messagebox.showerror("错误", "两次输入的密码不一致")
                return

            try:
                response = requests.post(f"{self.server_url}/register",
                                         json={"username": username, "password": password})
                data = response.json()

                if data.get("success"):
                    messagebox.showinfo("成功", "注册成功! 请登录")
                    dialog.destroy()
                else:
                    messagebox.showerror("错误", data.get("message", "注册失败"))
            except Exception as e:
                messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

        ttk.Button(dialog, text="注册", command=register).pack(pady=20)
        username_entry.focus()

    def import_project(self):
        """导入项目"""
        project_path = filedialog.askdirectory(title="选择项目目录")
        if project_path:
            self.current_project_path = project_path
            self.project_label.config(text=f"项目: {os.path.basename(project_path)}")
            self.update_file_tree()

    def new_file(self):
        """新建文件"""
        if not self.current_project_path:
            messagebox.showwarning("警告", "请先选择项目目录")
            return

        filename = tk.simpledialog.askstring("新建文件", "请输入文件名:")
        if filename:
            filepath = os.path.join(self.current_project_path, filename)
            try:
                with open(filepath, 'w') as f:
                    f.write("")
                self.update_file_tree()
            except Exception as e:
                messagebox.showerror("错误", f"创建文件失败: {str(e)}")

    def update_file_tree(self):
        """更新文件树"""
        if not self.current_project_path:
            return

        # 清空现有树
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        # 添加新项目
        for root, dirs, files in os.walk(self.current_project_path):
            relative_path = os.path.relpath(root, self.current_project_path)
            if relative_path == '.':
                parent = ''
            else:
                parent = relative_path.replace(os.path.sep, '/')

            node = self.file_tree.insert(parent, 'end', text=os.path.basename(root), values=[root], open=True)

            for file in files:
                file_path = os.path.join(root, file)
                self.file_tree.insert(node, 'end', text=file, values=[file_path])

    def on_file_select(self, event):
        """选择文件事件"""
        selected = self.file_tree.selection()
        if selected:
            file_path = self.file_tree.item(selected[0], "values")[0]
            if os.path.isfile(file_path):
                self.current_file_path = file_path
                self.file_label.config(text=f"文件: {os.path.basename(file_path)}")
                self.load_file_content(file_path)

    def load_file_content(self, file_path):
        """加载文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.code_editor.delete(1.0, tk.END)
            self.code_editor.insert(tk.END, content)
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败: {str(e)}")

    def save_file(self):
        """保存文件"""
        if not self.current_file_path:
            messagebox.showwarning("警告", "没有打开的文件")
            return

        try:
            content = self.code_editor.get(1.0, tk.END)
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("成功", "文件保存成功")
        except Exception as e:
            messagebox.showerror("错误", f"保存文件失败: {str(e)}")

    def run_code(self):
        """运行代码"""
        if not self.current_file_path:
            messagebox.showwarning("警告", "没有打开的文件")
            return

        # 保存当前文件
        self.save_file()

        # 执行Python文件
        command = f"python {self.current_file_path}"
        self.console_input.delete(0, tk.END)
        self.console_input.insert(0, command)
        self.execute_console_command(None)

    def submit_code(self):
        """提交代码到服务器"""
        if not self.current_file_path or not self.token:
            messagebox.showwarning("警告", "请先登录并打开文件")
            return

        try:
            with open(self.current_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.post(
                f"{self.server_url}/submit",
                json={
                    "filename": os.path.basename(self.current_file_path),
                    "content": content,
                    "project": os.path.basename(self.current_project_path) if self.current_project_path else None
                },
                headers=headers
            )
            data = response.json()

            if data.get("success"):
                messagebox.showinfo("成功", "代码提交成功")
            else:
                messagebox.showerror("错误", data.get("message", "提交失败"))
        except Exception as e:
            messagebox.showerror("错误", f"连接服务器失败: {str(e)}")

    def start_console_monitor(self):
        """启动控制台输出监控线程"""

        def monitor():
            while True:
                try:
                    output = self.console_queue.get(timeout=0.1)
                    self.root.after(0, self.update_console_output, output)
                except queue.Empty:
                    continue
                except:
                    break

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()

    def update_console_output(self, output):
        """更新控制台输出"""
        self.console_text.insert(tk.END, output)
        self.console_text.see(tk.END)

    def execute_console_command(self, event):
        """执行控制台命令"""
        command = self.console_input.get().strip()
        if not command:
            return

        self.console_input.delete(0, tk.END)

        # 显示命令
        self.console_text.insert(tk.END, f"$ {command}\n")
        self.console_text.see(tk.END)

        # 在后台线程执行命令
        def run_command():
            try:
                # 设置工作目录
                cwd = self.current_project_path if self.current_project_path else os.getcwd()

                # 执行命令
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True,
                    cwd=cwd, timeout=30
                )

                # 输出结果
                if result.stdout:
                    self.console_queue.put(result.stdout)
                if result.stderr:
                    self.console_queue.put(f"错误: {result.stderr}")

                self.console_queue.put(f"命令完成，返回码: {result.returncode}\n\n")

            except subprocess.TimeoutExpired:
                self.console_queue.put("命令执行超时\n\n")
            except Exception as e:
                self.console_queue.put(f"执行错误: {str(e)}\n\n")

        thread = threading.Thread(target=run_command, daemon=True)
        thread.start()

    def show_install_package_dialog(self):
        """显示安装包对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("安装Python包")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 100))

        ttk.Label(dialog, text="包名:").pack(pady=10)
        package_entry = ttk.Entry(dialog, width=40)
        package_entry.pack(pady=5)

        ttk.Label(dialog, text="版本 (可选):").pack(pady=(10, 0))
        version_entry = ttk.Entry(dialog, width=40)
        version_entry.pack(pady=5)

        def install():
            package_name = package_entry.get().strip()
            version = version_entry.get().strip()

            if not package_name:
                messagebox.showerror("错误", "包名不能为空")
                return

            # 构建安装命令
            if version:
                command = f"pip install {package_name}=={version}"
            else:
                command = f"pip install {package_name}"

            dialog.destroy()

            # 在控制台执行安装命令
            self.console_input.delete(0, tk.END)
            self.console_input.insert(0, command)
            self.execute_console_command(None)

            # 刷新已安装包列表
            self.root.after(3000, self.refresh_installed_packages)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="安装", command=install).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT)

        package_entry.focus()

    def list_packages(self):
        """列出已安装的包"""
        self.console_input.delete(0, tk.END)
        self.console_input.insert(0, "pip list")
        self.execute_console_command(None)

    def clear_console(self):
        """清空控制台"""
        self.console_text.delete(1.0, tk.END)
        self.console_text.insert(tk.END, "控制台已清空\n\n")

    def create_venv(self):
        """创建虚拟环境"""
        if not self.current_project_path:
            messagebox.showwarning("警告", "请先选择项目目录")
            return

        venv_name = tk.simpledialog.askstring("创建虚拟环境", "请输入虚拟环境名称:", initialvalue="venv")
        if venv_name:
            command = f"python -m venv {venv_name}"
            self.console_input.delete(0, tk.END)
            self.console_input.insert(0, command)
            self.execute_console_command(None)

    def search_packages(self, event):
        """搜索包"""
        query = self.search_entry.get().strip()
        if not query:
            return

        # 清空搜索结果
        self.search_listbox.delete(0, tk.END)
        self.search_listbox.insert(tk.END, "搜索中...")

        def search():
            try:
                # 使用pip search的替代方案 - 通过PyPI API搜索
                import urllib.request
                import urllib.parse

                url = f"https://pypi.org/simple/"
                # 这里简化处理，实际应该调用PyPI API
                # 由于pip search已被废弃，这里提供一个简单的实现

                self.root.after(0, lambda: self.search_listbox.delete(0, tk.END))
                self.root.after(0, lambda: self.search_listbox.insert(tk.END, f"搜索 '{query}' 的结果:"))
                self.root.after(0, lambda: self.search_listbox.insert(tk.END, f"{query} - 匹配的包"))
                self.root.after(0, lambda: self.search_listbox.insert(tk.END, "提示: 输入确切的包名进行安装"))

            except Exception as e:
                self.root.after(0, lambda: self.search_listbox.delete(0, tk.END))
                self.root.after(0, lambda: self.search_listbox.insert(tk.END, f"搜索失败: {str(e)}"))

        thread = threading.Thread(target=search, daemon=True)
        thread.start()

    def refresh_installed_packages(self):
        """刷新已安装包列表"""

        def get_packages():
            try:
                result = subprocess.run([sys.executable, "-m", "pip", "list"],
                                        capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')[2:]  # 跳过标题行
                packages = []
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            packages.append(f"{parts[0]} ({parts[1]})")

                self.root.after(0, self.update_installed_packages, packages)

            except Exception as e:
                self.root.after(0, self.update_installed_packages, [f"获取包列表失败: {str(e)}"])

        thread = threading.Thread(target=get_packages, daemon=True)
        thread.start()

    def update_installed_packages(self, packages):
        """更新已安装包列表"""
        self.installed_listbox.delete(0, tk.END)
        for package in packages:
            self.installed_listbox.insert(tk.END, package)

    def install_selected_package(self, event):
        """安装选中的包"""
        selection = self.search_listbox.curselection()
        if selection:
            package_info = self.search_listbox.get(selection[0])
            if "搜索" in package_info or "提示" in package_info or "失败" in package_info:
                return

            # 提取包名
            package_name = package_info.split()[0] if package_info else ""
            if package_name:
                command = f"pip install {package_name}"
                self.console_input.delete(0, tk.END)
                self.console_input.insert(0, command)
                self.execute_console_command(None)

                # 刷新已安装包列表
                self.root.after(3000, self.refresh_installed_packages)

    def uninstall_selected_package(self, event):
        """卸载选中的包"""
        selection = self.installed_listbox.curselection()
        if selection:
            package_info = self.installed_listbox.get(selection[0])
            package_name = package_info.split()[0] if package_info else ""

            if package_name and package_name not in ['pip', 'setuptools', 'wheel']:
                if messagebox.askyesno("确认卸载", f"确定要卸载 {package_name} 吗？"):
                    command = f"pip uninstall {package_name} -y"
                    self.console_input.delete(0, tk.END)
                    self.console_input.insert(0, command)
                    self.execute_console_command(None)

                    # 刷新已安装包列表
                    self.root.after(3000, self.refresh_installed_packages)
            else:
                messagebox.showwarning("警告", "不能卸载系统关键包")


if __name__ == "__main__":
    root = tk.Tk()
    app = PythonIDEClient(root)
    root.mainloop()