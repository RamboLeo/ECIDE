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
# 服务器配置部分
self.server_url = "http://localhost:8081/api"  # 后端API地址
self.token = None  # 用户认证token
self.current_user = None  # 当前登录用户
self.current_project_path = None  # 当前项目路径
self.current_file_path = None  # 当前打开文件路径

# 控制台相关属性
self.console_process = None  # 控制台进程
self.console_queue = queue.Queue()  # 控制台输出队列

# 创建界面组件
self.create_widgets()

# 启动控制台输出监控线程
self.start_console_monitor()


# 创建界面组件的方法
def create_widgets(self):
    # 创建主框架 - 作为所有其他组件的容器
    main_frame = ttk.Frame(self.root)  # ttk是Tkinter的主题扩展
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)  # 填充整个窗口

    # 顶部工具栏框架
    toolbar_frame = ttk.Frame(main_frame)
    toolbar_frame.pack(fill=tk.X, pady=(0, 10))  # 水平填充，下方有10像素间距

    # 登录状态标签
    self.status_label = ttk.Label(toolbar_frame, text="未登录")
    self.status_label.pack(side=tk.LEFT)  # 左对齐

    # 项目路径标签 - 显示蓝色文字
    self.project_label = ttk.Label(toolbar_frame, text="未选择项目", foreground="blue")
    self.project_label.pack(side=tk.LEFT, padx=(20, 0))  # 左侧有20像素间距

    # 注册按钮 - 点击时调用show_register_dialog方法
    self.register_btn = ttk.Button(toolbar_frame, text="注册", command=self.show_register_dialog)
    self.register_btn.pack(side=tk.LEFT)  # 左对齐对齐

    # 登录按钮
    self.login_btn = ttk.Button(toolbar_frame, text="登录", command=self.show_login_dialog)
    self.login_btn.pack(side=tk.RIGHT, padx=(0, 0))  # 右侧无间距

    # 管理按钮 - 管理员登录
    self.login_btn = ttk.Button(toolbar_frame, text="管理登录", command=self.show_login_dialog)
    self.login_btn.pack(side=tk.RIGHT, padx=(0, 0))

    # 主要内容区域 - 使用PanedWindow实现可调整的分割布局
    main_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)  # 水平分割
    main_paned.pack(fill=tk.BOTH, expand=True)  # 填充剩余空间

    # 左侧面板 - 项目文件树
    left_frame = ttk.LabelFrame(main_paned, text="项目文件", width=300)  # 带标签的框架
    main_paned.add(left_frame, weight=1)  # 添加到分割窗口，weight表示分配的空间比例

    # 项目操作按钮框架
    project_btn_frame = ttk.Frame(left_frame)
    project_btn_frame.pack(fill=tk.X, padx=5, pady=5)  # 水平填充，有内边距

    # 导入项目按钮
    ttk.Button(project_btn_frame, text="导入项目", command=self.import_project).pack(side=tk.LEFT)
    # 新建文件按钮
    ttk.Button(project_btn_frame, text="新建文件", command=self.new_file).pack(side=tk.LEFT, padx=(5, 0))

    # 文件树组件 - 用于显示项目文件结构
    self.file_tree = ttk.Treeview(left_frame)
    self.file_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)  # 填充剩余空间
    # 绑定双击事件 - 双击文件时调用on_file_select方法
    self.file_tree.bind("<Double-1>", self.on_file_select)

    # 右侧区域 - 使用垂直分割
    right_paned = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
    main_paned.add(right_paned, weight=3)  # 右侧区域占3/4空间

    # 代码编辑区域框架
    editor_frame = ttk.Frame(right_paned)
    right_paned.add(editor_frame, weight=2)  # 编辑器占2/3高度

    # 编辑器工具栏
    editor_toolbar = ttk.Frame(editor_frame)
    editor_toolbar.pack(fill=tk.X, pady=(0, 5))  # 水平填充，下方有5像素间距

    # 当前文件标签
    self.file_label = ttk.Label(editor_toolbar, text="未打开文件")
    self.file_label.pack(side=tk.LEFT)

    # 保存按钮 - 调用save_file方法
    ttk.Button(editor_toolbar, text="保存", command=self.save_file).pack(side=tk.RIGHT, padx=(0, 0))
    # 运行按钮 - 调用run_code方法
    ttk.Button(editor_toolbar, text="运行", command=self.run_code).pack(side=tk.RIGHT, padx=(0, 0))
    # 提交按钮 - 调用submit_code方法
    ttk.Button(editor_toolbar, text="提交到服务器", command=self.submit_code).pack(side=tk.RIGHT, padx=(0, 0))

    # 代码编辑器 - 使用ScrolledText实现带滚动条的文本编辑器
    self.code_editor = scrolledtext.ScrolledText(editor_frame, wrap=tk.NONE, font=("Consolas", 11))
    self.code_editor.pack(fill=tk.BOTH, expand=True)  # 填充剩余空间

    # 底部区域 - 使用Notebook实现标签页
    bottom_notebook = ttk.Notebook(right_paned)
    right_paned.add(bottom_notebook, weight=1)  # 占1/3高度

    # 输出页面框架
    output_frame = ttk.Frame(bottom_notebook)
    bottom_notebook.add(output_frame, text="程序输出")  # 添加标签页

    # 输出文本框
    self.output_text = scrolledtext.ScrolledText(output_frame, height=8, font=("Consolas", 10))
    self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # 控制台页面框架
    console_frame = ttk.Frame(bottom_notebook)
    bottom_notebook.add(console_frame, text="控制台")

    # 控制台工具栏
    console_toolbar = ttk.Frame(console_frame)
    console_toolbar.pack(fill=tk.X, padx=5, pady=(5, 0))  # 水平填充

    # 控制台功能按钮
    ttk.Button(console_toolbar, text="安装库", command=self.show_install_package_dialog).pack(side=tk.LEFT)
    ttk.Button(console_toolbar, text="列出已安装", command=self.list_packages).pack(side=tk.LEFT, padx=(5, 0))
    ttk.Button(console_toolbar, text="清空", command=self.clear_console).pack(side=tk.LEFT, padx=(5, 0))
    ttk.Button(console_toolbar, text="创建虚拟环境", command=self.create_venv).pack(side=tk.LEFT, padx=(5, 0))

    # 控制台输出文本框 - 黑色背景绿色文字
    self.console_text = scrolledtext.ScrolledText(console_frame, height=8, font=("Consolas", 10),
                                                  background="black", foreground="green")
    self.console_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # 控制台输入框架
    console_input_frame = ttk.Frame(console_frame)
    console_input_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

    # 输入提示符
    ttk.Label(console_input_frame, text="$").pack(side=tk.LEFT)
    # 命令行输入框
    self.console_input = ttk.Entry(console_input_frame, font=("Consolas", 10))
    self.console_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
    # 绑定回车键事件 - 执行命令
    self.console_input.bind("<Return>", self.execute_console_command)

    # 执行按钮
    ttk.Button(console_input_frame, text="执行", command=lambda: self.execute_console_command(None)).pack(side=tk.RIGHT,
                                                                                                          padx=(5, 0))

    # 包管理页面框架
    package_frame = ttk.Frame(bottom_notebook)
    bottom_notebook.add(package_frame, text="包管理")

    # 包管理工具栏
    package_toolbar = ttk.Frame(package_frame)
    package_toolbar.pack(fill=tk.X, padx=5, pady=5)

    # 搜索包标签和输入框
    ttk.Label(package_toolbar, text="搜索包:").pack(side=tk.LEFT)
    self.search_entry = ttk.Entry(package_toolbar, width=30)
    self.search_entry.pack(side=tk.LEFT, padx=(5, 0))
    self.search_entry.bind("<Return>", self.search_packages)  # 回车搜索

    # 搜索按钮
    ttk.Button(package_toolbar, text="搜索", command=lambda: self.search_packages(None)).pack(side=tk.LEFT, padx=(5, 0))
    ttk.Button(package_toolbar, text="刷新已安装", command=self.refresh_installed_packages).pack(side=tk.LEFT,
                                                                                                 padx=(5, 0))

    # 包列表框架
    package_list_frame = ttk.Frame(package_frame)
    package_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # 已安装包列表框架
    installed_frame = ttk.LabelFrame(package_list_frame, text="已安装的包")
    installed_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

    # 已安装包列表框
    self.installed_listbox = tk.Listbox(installed_frame, font=("Consolas", 9))
    self.installed_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    # 双击卸载包
    self.installed_listbox.bind("<Double-1>", self.uninstall_selected_package)

    # 搜索结果框架
    search_frame = ttk.LabelFrame(package_list_frame, text="搜索结果")
    search_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

    # 搜索结果列表框
    self.search_listbox = tk.Listbox(search_frame, font=("Consolas", 9))
    self.search_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    # 双击安装包
    self.search_listbox.bind("<Double-1>", self.install_selected_package)

    # 初始化控制台输出
    self.console_text.insert(tk.END, "Python IDE 控制台 v2.0\n")
    self.console_text.insert(tk.END, "=" * 50 + "\n")
    self.console_text.insert(tk.END, "提示: 双击已安装包可卸载，双击搜索结果可安装\n\n")

    # 加载已安装的Python包
    self.refresh_installed_packages()