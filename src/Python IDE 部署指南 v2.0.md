# Python IDE 部署指南 v2.0

## 项目概述

这是一个Python集成开发工具，包含客户端和服务器端两个部分。客户端提供代码编辑、项目管理、本地运行、控制台指令和包管理功能，服务器端负责用户认证和代码存储。

## 版本说明

- **v1.0**: 基础IDE功能（代码编辑、项目管理、用户认证）
- **v2.0**: 新增控制台指令、包管理、虚拟环境支持

## 系统架构

- **客户端**: Python Tkinter GUI应用，支持用户登录、项目导入、代码编辑、提交和控制台操作
- **服务器端**: Flask Web应用，提供RESTful API接口
- **数据库**: SQLite，存储用户信息和代码提交记录

## 服务器端部署

### 环境要求

- Python 3.11+
- pip包管理器
- 网络连接

### 部署步骤

1. **下载项目文件**
   ```bash
   # 将python_ide_server文件夹复制到服务器
   ```

2. **安装依赖**
   ```bash
   cd python_ide_server
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **配置环境**
   - 修改`src/routes/user.py`中的JWT_SECRET为安全的密钥
   - 根据需要修改数据库配置

4. **启动服务**
   ```bash
   python src/main.py
   ```
   
   服务将在`http://0.0.0.0:5000`启动

### API接口

- `POST /api/register` - 用户注册
- `POST /api/login` - 用户登录
- `POST /api/submit_code` - 提交代码（需要认证）
- `GET /api/my_submissions` - 获取我的提交记录（需要认证）

## 客户端部署

### 环境要求

- Python 3.11+
- tkinter库（通常随Python安装）
- requests库

### 安装步骤

1. **安装系统依赖**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install python3-tk
   
   # CentOS/RHEL
   sudo yum install tkinter
   
   # macOS (使用Homebrew)
   brew install python-tk
   ```

2. **安装Python依赖**
   ```bash
   pip install requests
   ```

3. **运行客户端**
   ```bash
   # 运行v1.0版本
   python python_ide_client.py
   
   # 运行v2.0版本（推荐）
   python python_ide_client_v2.py
   ```

## 客户端功能对比

### v1.0 基础功能
- **用户认证**: 注册和登录功能
- **项目管理**: 导入本地Python项目文件夹
- **代码编辑**: 基本的代码编辑器
- **本地运行**: 在本地环境运行Python代码
- **代码提交**: 将代码提交到服务器存储

### v2.0 增强功能
- **集成控制台**: 在IDE内执行系统命令和Python命令
- **包管理系统**: 图形化管理Python包的安装和卸载
- **虚拟环境支持**: 创建和管理项目专用的Python环境
- **多标签页界面**: 更好的用户体验和界面布局
- **实时命令执行**: 异步执行命令，不阻塞界面

## v2.0 使用指南

### 控制台功能
1. 切换到"控制台"标签页
2. 在输入框中输入命令（如：`pip install requests`）
3. 按Enter键或点击"执行"按钮
4. 查看命令执行结果

#### 常用命令示例：
```bash
# 包管理
pip install numpy pandas matplotlib
pip list
pip show requests
pip uninstall package_name

# 虚拟环境
python -m venv myproject_env
source myproject_env/bin/activate  # Linux/Mac
myproject_env\Scripts\activate     # Windows

# 文件操作
ls -la
mkdir new_folder
touch new_file.py

# Python执行
python script.py
python -c "print('Hello World')"
```

### 包管理功能
1. 切换到"包管理"标签页
2. 查看"已安装的包"列表
3. 双击包名可以卸载该包
4. 在搜索框中输入包名进行搜索
5. 双击搜索结果可以安装该包

### 虚拟环境管理
1. 导入项目后，点击"创建虚拟环境"按钮
2. 输入虚拟环境名称
3. 等待创建完成
4. 使用控制台命令激活虚拟环境

## 配置说明

### 服务器配置

在客户端代码中，服务器地址配置为：
```python
self.server_url = "http://localhost:5000/api"
```

如果服务器部署在其他地址，需要修改此配置。

### 安全配置

- 修改JWT密钥：在`src/routes/user.py`中更改`JWT_SECRET`
- 配置HTTPS：在生产环境中建议使用HTTPS
- 数据库安全：考虑使用更安全的数据库系统

## 故障排除

### 常见问题

1. **连接服务器失败**
   - 检查服务器是否正常运行
   - 确认网络连接
   - 验证服务器地址配置

2. **登录失败**
   - 确认用户名和密码正确
   - 检查服务器日志

3. **代码提交失败**
   - 确认已登录
   - 检查网络连接
   - 验证token有效性

4. **控制台命令无响应**（v2.0）
   - 检查命令是否正确
   - 确认网络连接（对于需要网络的命令）
   - 重启IDE客户端

5. **包安装失败**（v2.0）
   - 检查网络连接
   - 确认包名拼写正确
   - 尝试使用控制台直接执行pip命令

6. **tkinter模块未找到**
   - 安装python3-tk包：`sudo apt-get install python3-tk`
   - 确认Python版本支持tkinter

### 日志查看

服务器运行时会在控制台输出日志信息，可以通过日志排查问题。

## 性能优化建议

### 客户端优化
- 定期清理控制台输出以节省内存
- 避免同时执行多个耗时命令
- 合理使用虚拟环境隔离项目依赖

### 服务器端优化
- 配置适当的数据库连接池
- 使用生产级WSGI服务器（如Gunicorn）
- 配置反向代理（如Nginx）

## 扩展功能

### 可能的改进

1. **代码语法高亮**: 集成更好的代码编辑器
2. **多语言支持**: 支持除Python外的其他编程语言
3. **协作功能**: 支持多用户协作编辑
4. **版本控制**: 集成Git版本控制
5. **插件系统**: 支持第三方插件扩展
6. **代码调试**: 集成调试器功能
7. **智能补全**: 代码自动补全功能

### 技术升级

1. **Web客户端**: 开发基于Web的客户端界面
2. **数据库升级**: 使用PostgreSQL或MySQL
3. **容器化部署**: 使用Docker进行部署
4. **微服务架构**: 拆分为多个微服务
5. **云端集成**: 支持云端代码执行和存储

## 技术支持

如有问题，请检查：
1. Python版本兼容性
2. 依赖包安装情况
3. 网络连接状态
4. 服务器运行状态
5. 系统权限设置

## 更新日志

### v2.0 (当前版本)
- ✅ 新增集成控制台功能
- ✅ 新增包管理系统
- ✅ 新增虚拟环境支持
- ✅ 改进用户界面布局
- ✅ 增强错误处理机制

### v1.0
- ✅ 基础IDE功能
- ✅ 用户认证系统
- ✅ 代码编辑和运行
- ✅ 服务器代码提交

