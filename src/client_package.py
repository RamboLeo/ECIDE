#!/usr/bin/env python3
"""
Python IDE 客户端打包脚本
使用PyInstaller将客户端打包为可执行文件
"""

import os
import sys
import subprocess
import shutil

def install_pyinstaller():
    """安装PyInstaller"""
    print("正在安装PyInstaller...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✓ PyInstaller安装成功")
        return True
    except subprocess.CalledProcessError:
        print("✗ PyInstaller安装失败")
        return False

def create_spec_file():
    """创建PyInstaller规格文件"""
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['python_ide_client.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['requests', 'tkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PythonIDE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
'''
    
    with open('python_ide_client.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content.strip())
    
    print("✓ 规格文件创建成功")

def build_executable():
    """构建可执行文件"""
    print("正在构建可执行文件...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "PyInstaller", 
            "--onefile", 
            "--windowed",
            "--name=PythonIDE",
            "python_ide_client.py"
        ])
        print("✓ 可执行文件构建成功")
        return True
    except subprocess.CalledProcessError:
        print("✗ 可执行文件构建失败")
        return False

def create_installer_script():
    """创建安装脚本"""
    installer_content = '''#!/bin/bash
# Python IDE 客户端安装脚本

echo "Python IDE 客户端安装程序"
echo "========================="

# 检查操作系统
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    OS="windows"
else
    echo "不支持的操作系统: $OSTYPE"
    exit 1
fi

echo "检测到操作系统: $OS"

# 创建安装目录
INSTALL_DIR="$HOME/PythonIDE"
mkdir -p "$INSTALL_DIR"

# 复制文件
echo "正在安装文件..."
cp PythonIDE "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/PythonIDE"

# 创建桌面快捷方式 (Linux)
if [[ "$OS" == "linux" ]]; then
    DESKTOP_FILE="$HOME/Desktop/PythonIDE.desktop"
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Python IDE
Comment=Python集成开发环境客户端
Exec=$INSTALL_DIR/PythonIDE
Icon=applications-development
Terminal=false
Categories=Development;IDE;
EOF
    chmod +x "$DESKTOP_FILE"
    echo "✓ 桌面快捷方式已创建"
fi

echo "安装完成!"
echo "可执行文件位置: $INSTALL_DIR/PythonIDE"

if [[ "$OS" == "linux" ]]; then
    echo "桌面快捷方式已创建"
fi

echo ""
echo "使用说明:"
echo "1. 确保服务器端正在运行"
echo "2. 运行客户端程序"
echo "3. 注册或登录账号"
echo "4. 导入Python项目开始使用"
'''
    
    with open('install.sh', 'w', encoding='utf-8') as f:
        f.write(installer_content.strip())
    
    os.chmod('install.sh', 0o755)
    print("✓ 安装脚本创建成功")

def create_readme():
    """创建README文件"""
    readme_content = '''# Python IDE 客户端

## 简介

这是一个Python集成开发环境的客户端应用程序，提供以下功能：

- 用户注册和登录
- Python项目导入和管理
- 代码编辑和语法高亮
- 本地代码运行
- 代码提交到服务器

## 系统要求

- 操作系统: Windows, macOS, Linux
- 网络连接（用于与服务器通信）

## 安装方法

### 方法1: 使用安装脚本 (推荐)

```bash
chmod +x install.sh
./install.sh
```

### 方法2: 手动安装

1. 将 `PythonIDE` 可执行文件复制到您选择的目录
2. 双击运行或在终端中执行

## 使用说明

1. **启动应用**: 双击 `PythonIDE` 或在终端中运行
2. **用户认证**: 首次使用请点击"注册"创建账号，之后使用"登录"
3. **导入项目**: 点击"导入项目"选择本地Python项目文件夹
4. **编辑代码**: 在左侧文件树中双击Python文件进行编辑
5. **运行代码**: 点击"运行"按钮在本地执行当前文件
6. **提交代码**: 点击"提交到服务器"将代码保存到服务器

## 配置

默认服务器地址为 `http://localhost:5000`。如果服务器部署在其他地址，需要修改客户端配置。

## 故障排除

1. **无法连接服务器**: 检查服务器是否运行，网络是否正常
2. **登录失败**: 确认用户名密码正确
3. **无法导入项目**: 确保选择的是包含Python文件的文件夹

## 技术支持

如遇问题，请检查：
- 网络连接状态
- 服务器运行状态
- 防火墙设置

## 版本信息

版本: 1.0.0
构建日期: ''' + str(__import__('datetime').datetime.now().strftime('%Y-%m-%d')) + '''
'''
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content.strip())
    
    print("✓ README文件创建成功")

def main():
    """主函数"""
    print("Python IDE 客户端打包工具")
    print("=" * 30)
    
    # 检查客户端文件是否存在
    if not os.path.exists('python_ide_client.py'):
        print("✗ 找不到客户端文件 python_ide_client.py")
        return False
    
    # 安装PyInstaller
    if not install_pyinstaller():
        return False
    
    # 创建规格文件
    create_spec_file()
    
    # 构建可执行文件
    if not build_executable():
        return False
    
    # 创建安装脚本
    create_installer_script()
    
    # 创建README
    create_readme()
    
    print("\n" + "=" * 30)
    print("打包完成!")
    print("生成的文件:")
    print("- dist/PythonIDE (可执行文件)")
    print("- install.sh (安装脚本)")
    print("- README.md (使用说明)")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

