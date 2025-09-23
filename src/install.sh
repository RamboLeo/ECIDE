#!/bin/bash
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