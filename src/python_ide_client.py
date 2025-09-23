import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import requests
import json
import os
import subprocess
import sys
from pathlib import Path

class PythonIDEClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Python IDE 客户端")
        self.root.geometry("1200x800")
        
        # 服务器配置
        self.server_url = "http://localhost:5000/api"
        self.token = None
        self.current_user = None
        self.current_project_path = None
        self.current_file_path = None
        
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
        self.status_label = ttk.Label(toolbar_frame, text="未登录")
        self.status_label.pack(side=tk.LEFT)
        
        # 登录按钮
        self.login_btn = ttk.Button(toolbar_frame, text="登录", command=self.show_login_dialog)
        self.login_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # 注册按钮
        self.register_btn = ttk.Button(toolbar_frame, text="注册", command=self.show_register_dialog)
        self.register_btn.pack(side=tk.RIGHT)
        
        # 主要内容区域
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧面板 - 项目文件树
        left_frame = ttk.LabelFrame(content_frame, text="项目文件", width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)
        
        # 项目操作按钮
        project_btn_frame = ttk.Frame(left_frame)
        project_btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(project_btn_frame, text="导入项目", command=self.import_project).pack(side=tk.LEFT)
        ttk.Button(project_btn_frame, text="新建文件", command=self.new_file).pack(side=tk.LEFT, padx=(5, 0))
        
        # 文件树
        self.file_tree = ttk.Treeview(left_frame)
        self.file_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.file_tree.bind("<Double-1>", self.on_file_select)
        
        # 右侧面板 - 代码编辑器
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 编辑器工具栏
        editor_toolbar = ttk.Frame(right_frame)
        editor_toolbar.pack(fill=tk.X, pady=(0, 5))
        
        self.file_label = ttk.Label(editor_toolbar, text="未打开文件")
        self.file_label.pack(side=tk.LEFT)
        
        ttk.Button(editor_toolbar, text="保存", command=self.save_file).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(editor_toolbar, text="运行", command=self.run_code).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(editor_toolbar, text="提交到服务器", command=self.submit_code).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 代码编辑器
        self.code_editor = scrolledtext.ScrolledText(right_frame, wrap=tk.NONE, font=("Consolas", 11))
        self.code_editor.pack(fill=tk.BOTH, expand=True)
        
        # 底部输出面板
        output_frame = ttk.LabelFrame(main_frame, text="输出", height=150)
        output_frame.pack(fill=tk.X, pady=(10, 0))
        output_frame.pack_propagate(False)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, height=8, font=("Consolas", 10))
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def show_login_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("用户登录")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
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
                    self.token = data.get("token")
                    self.current_user = data.get("user")
                    self.status_label.config(text=f"已登录: {username}")
                    self.login_btn.config(text="退出登录", command=self.logout)
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
        
    def show_register_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("用户注册")
        dialog.geometry("300x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        ttk.Label(dialog, text="用户名:").pack(pady=10)
        username_entry = ttk.Entry(dialog, width=30)
        username_entry.pack(pady=5)
        
        ttk.Label(dialog, text="密码:").pack(pady=(10, 0))
        password_entry = ttk.Entry(dialog, width=30, show="*")
        password_entry.pack(pady=5)
        
        ttk.Label(dialog, text="确认密码:").pack(pady=(10, 0))
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
        
    def logout(self):
        self.token = None
        self.current_user = None
        self.status_label.config(text="未登录")
        self.login_btn.config(text="登录", command=self.show_login_dialog)
        messagebox.showinfo("提示", "已退出登录")
        
    def import_project(self):
        folder_path = filedialog.askdirectory(title="选择项目文件夹")
        if folder_path:
            self.current_project_path = folder_path
            self.load_project_files(folder_path)
            
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
        
    def add_files_to_tree(self, folder_path, parent_item):
        try:
            for item in sorted(os.listdir(folder_path)):
                if item.startswith('.'):  # 跳过隐藏文件
                    continue
                    
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
            # 在文件所在目录运行Python脚本
            result = subprocess.run([sys.executable, self.current_file_path], 
                                  capture_output=True, text=True, 
                                  cwd=os.path.dirname(self.current_file_path))
            
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
    # 导入tkinter.simpledialog
    import tkinter.simpledialog
    
    root = tk.Tk()
    app = PythonIDEClient(root)
    root.mainloop()

