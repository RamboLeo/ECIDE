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
        self.root.geometry("1300x600")

        # 服务器配置
        self.server_url = "http://localhost:8081/api"
        self.token = None
        self.admin_token = None  # 新增管理员token
        self.current_user = None
        self.current_admin = None  # 新增当前管理员
        self.current_project_path = None
        self.current_file_path = None

        # 文件排序设置
        self.sort_ascending = True  # 默认升序排列

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

        # 排序按钮
        sort_frame = ttk.Frame(left_frame)
        sort_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ttk.Button(sort_frame, text="升序排列", command=self.sort_ascending_order).pack(side=tk.LEFT)
        ttk.Button(sort_frame, text="降序排列", command=self.sort_descending_order).pack(side=tk.LEFT, padx=(5, 0))

        # 创建包含滚动条的文件树框架
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 垂直滚动条
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        # 水平滚动条
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        # 文件树
        self.file_tree = ttk.Treeview(tree_frame,
                                      yscrollcommand=vsb.set,
                                      xscrollcommand=hsb.set)
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 配置滚动条
        vsb.config(command=self.file_tree.yview)
        hsb.config(command=self.file_tree.xview)

        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

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

    def sort_ascending_order(self):
        """设置升序排列并刷新文件树"""
        self.sort_ascending = True
        if self.current_project_path:
            self.load_project_files(self.current_project_path)
            messagebox.showinfo("排序", "已设置为升序排列")

    def sort_descending_order(self):
        """设置降序排列并刷新文件树"""
        self.sort_ascending = False
        if self.current_project_path:
            self.load_project_files(self.current_project_path)
            messagebox.showinfo("排序", "已设置为降序排列")

    def add_files_to_tree(self, folder_path, parent_item):
        """添加文件和文件夹到树中，根据排序设置进行排序"""
        try:
            items = []
            for item in os.listdir(folder_path):
                if item.startswith('.'):  # 跳过隐藏文件
                    continue
                items.append(item)

            # 根据排序设置进行排序
            if self.sort_ascending:
                items.sort()  # 升序排列
            else:
                items.sort(reverse=True)  # 降序排列

            for item in items:
                item_path = os.path.join(folder_path, item)

                if os.path.isdir(item_path):
                    # 文件夹
                    folder_item = self.file_tree.insert(parent_item, "end", text=f"📁 {item}", values=[item_path])
                    self.add_files_to_tree(item_path, folder_item)
                else:
                    # 文件
                    icon = "🐍" if item.endswith('.py') else "📄"
                    self.file_tree.insert(parent_item, "end", text=f"{icon} {item}", values=[item_path])
        except PermissionError:
            pass

    # 其他方法保持不变...
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
            messagebox.showinfo("提示", "您已经是管理员")
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
        self.admin_token = None
        self.current_admin = None
        self.admin_status_label.config(text="管理员: 未登录", foreground="red")
        self.admin_login_btn.config(text="管理登录", command=self.show_admin_login_dialog)
        messagebox.showinfo("提示", "已退出管理员登录")

    # 其他方法保持不变...
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

    # 其他原有方法保持不变...
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
                                        capture_output=True, text=True, encoding='utf-8')  # 添加编码参数
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

    def import_project(self):
        folder_path = filedialog.askdirectory(title="选择项目文件夹")
        if folder_path:
            self.current_project_path = folder_path
            self.project_label.config(text=f"项目: {os.path.basename(folder_path)}")
            self.load_project_files(folder_path)

            # 在控制台显示项目信息
            self.console_text.insert(tk.END, f"已导入项目: {folder_path}\n")
            self.console_text.insert(tk.END, f"工作目录已切换到: {folder_path}\n\n")
            self.console_text.see(tk.END)

    def load_project_files(self, folder_path):
        # 清空文件树
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        # 添加项目根目录
        project_name = os.path.basename(folder_path)
        root_item = self.file_tree.insert("", "end", text=project_name, values=[folder_path])

        # 递归添加文件和文件夹
        self.add_files_to_tree(folder_path, root_item)

        # 展开根目录
        self.file_tree.item(root_item, open=True)

    def on_file_select(self, event):
        selection = self.file_tree.selection()
        if selection:
            item = selection[0]
            file_path = self.file_tree.item(item, "values")[0]

            if os.path.isfile(file_path) and file_path.endswith('.py'):
                self.open_file(file_path)

    def open_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.code_editor.delete(1.0, tk.END)
            self.code_editor.insert(1.0, content)
            self.current_file_path = file_path
            self.file_label.config(text=f"当前文件: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件: {str(e)}")

    def new_file(self):
        if not self.current_project_path:
            messagebox.showwarning("警告", "请先导入项目")
            return

        filename = tk.simpledialog.askstring("新建文件", "请输入文件名 (例如: main.py):")
        if filename:
            if not filename.endswith('.py'):
                filename += '.py'

            file_path = os.path.join(self.current_project_path, filename)
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("# 新建的Python文件\n\n")

                self.load_project_files(self.current_project_path)
                self.open_file(file_path)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建文件: {str(e)}")

    def save_file(self):
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
        if not self.current_file_path:
            messagebox.showwarning("警告", "没有打开的文件")
            return

        # 先保存文件
        self.save_file()

        # 清空输出
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, f"运行文件: {self.current_file_path}\n")
        self.output_text.insert(tk.END, "=" * 50 + "\n")

        try:
            # 在文件所在目录运行Python脚本，并显式指定编码为utf-8
            result = subprocess.run(
                [sys.executable, self.current_file_path],
                capture_output=True,
                text=True,
                encoding='utf-8',  # 显式指定编码
                cwd=os.path.dirname(self.current_file_path)
            )

            if result.stdout:
                self.output_text.insert(tk.END, "输出:\n")
                self.output_text.insert(tk.END, result.stdout)

            if result.stderr:
                self.output_text.insert(tk.END, "\n错误:\n")
                self.output_text.insert(tk.END, result.stderr)

            self.output_text.insert(tk.END, f"\n程序退出，返回码: {result.returncode}\n")

        except Exception as e:
            self.output_text.insert(tk.END, f"运行失败: {str(e)}\n")

        # 滚动到底部
        self.output_text.see(tk.END)

    def submit_code(self):
        if not self.token:
            messagebox.showwarning("警告", "请先登录")
            return

        if not self.current_file_path or not self.current_project_path:
            messagebox.showwarning("警告", "请先打开项目和文件")
            return

        # 先保存文件
        self.save_file()

        try:
            # 获取代码内容
            content = self.code_editor.get(1.0, tk.END)

            # 计算相对路径
            rel_path = os.path.relpath(self.current_file_path, self.current_project_path)
            project_name = os.path.basename(self.current_project_path)

            # 提交到服务器
            headers = {"Authorization": f"Bearer {self.token}"}
            data = {
                "project_name": project_name,
                "file_path": rel_path,
                "code_content": content
            }

            response = requests.post(f"{self.server_url}/submit_code",
                                     json=data, headers=headers)
            result = response.json()

            if result.get("success"):
                messagebox.showinfo("成功", "代码提交成功!")
            else:
                messagebox.showerror("错误", result.get("message", "提交失败"))

        except Exception as e:
            messagebox.showerror("错误", f"提交失败: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = PythonIDEClient(root)
    root.mainloop()