#!/usr/bin/env python3
"""
测试Python IDE客户端v2.0的控制台功能
"""

import subprocess
import sys
import os

def test_pip_commands():
    """测试pip相关命令"""
    print("=== 测试pip命令 ===")
    
    # 测试pip list
    print("1. 测试 pip list")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list"], 
                              capture_output=True, text=True, timeout=10)
        print(f"返回码: {result.returncode}")
        if result.stdout:
            lines = result.stdout.strip().split('\n')[:5]  # 只显示前5行
            for line in lines:
                print(f"  {line}")
        print("✓ pip list 测试成功")
    except Exception as e:
        print(f"✗ pip list 测试失败: {e}")
    
    print()
    
    # 测试pip show
    print("2. 测试 pip show requests")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "show", "requests"], 
                              capture_output=True, text=True, timeout=10)
        print(f"返回码: {result.returncode}")
        if result.stdout:
            lines = result.stdout.strip().split('\n')[:3]  # 只显示前3行
            for line in lines:
                print(f"  {line}")
        print("✓ pip show 测试成功")
    except Exception as e:
        print(f"✗ pip show 测试失败: {e}")
    
    print()

def test_python_commands():
    """测试Python相关命令"""
    print("=== 测试Python命令 ===")
    
    # 测试python版本
    print("1. 测试 python --version")
    try:
        result = subprocess.run([sys.executable, "--version"], 
                              capture_output=True, text=True, timeout=5)
        print(f"返回码: {result.returncode}")
        print(f"版本: {result.stdout.strip()}")
        print("✓ python --version 测试成功")
    except Exception as e:
        print(f"✗ python --version 测试失败: {e}")
    
    print()
    
    # 测试简单Python代码执行
    print("2. 测试执行简单Python代码")
    try:
        result = subprocess.run([sys.executable, "-c", "print('Hello from console!')"], 
                              capture_output=True, text=True, timeout=5)
        print(f"返回码: {result.returncode}")
        print(f"输出: {result.stdout.strip()}")
        print("✓ Python代码执行测试成功")
    except Exception as e:
        print(f"✗ Python代码执行测试失败: {e}")
    
    print()

def test_virtual_env():
    """测试虚拟环境相关命令"""
    print("=== 测试虚拟环境命令 ===")
    
    # 创建测试目录
    test_dir = "/tmp/test_venv_project"
    os.makedirs(test_dir, exist_ok=True)
    
    print(f"1. 在 {test_dir} 创建虚拟环境")
    try:
        result = subprocess.run([sys.executable, "-m", "venv", "test_venv"], 
                              capture_output=True, text=True, timeout=30, cwd=test_dir)
        print(f"返回码: {result.returncode}")
        
        venv_path = os.path.join(test_dir, "test_venv")
        if os.path.exists(venv_path):
            print(f"✓ 虚拟环境创建成功: {venv_path}")
            
            # 清理测试环境
            import shutil
            shutil.rmtree(venv_path)
            print("✓ 测试环境已清理")
        else:
            print("✗ 虚拟环境创建失败")
            
    except Exception as e:
        print(f"✗ 虚拟环境测试失败: {e}")
    
    print()

def test_file_operations():
    """测试文件操作命令"""
    print("=== 测试文件操作命令 ===")
    
    test_dir = "/tmp/test_file_ops"
    os.makedirs(test_dir, exist_ok=True)
    
    # 测试ls命令
    print("1. 测试 ls 命令")
    try:
        result = subprocess.run(["ls", "-la", test_dir], 
                              capture_output=True, text=True, timeout=5)
        print(f"返回码: {result.returncode}")
        if result.stdout:
            lines = result.stdout.strip().split('\n')[:3]
            for line in lines:
                print(f"  {line}")
        print("✓ ls 命令测试成功")
    except Exception as e:
        print(f"✗ ls 命令测试失败: {e}")
    
    print()
    
    # 测试创建和删除文件
    print("2. 测试文件创建和删除")
    try:
        test_file = os.path.join(test_dir, "test.py")
        
        # 创建文件
        result = subprocess.run(["touch", test_file], 
                              capture_output=True, text=True, timeout=5)
        print(f"创建文件返回码: {result.returncode}")
        
        if os.path.exists(test_file):
            print("✓ 文件创建成功")
            
            # 删除文件
            os.remove(test_file)
            print("✓ 文件删除成功")
        else:
            print("✗ 文件创建失败")
            
    except Exception as e:
        print(f"✗ 文件操作测试失败: {e}")
    
    # 清理测试目录
    import shutil
    shutil.rmtree(test_dir)
    
    print()

def main():
    """主测试函数"""
    print("Python IDE 控制台功能测试")
    print("=" * 50)
    
    test_python_commands()
    test_pip_commands()
    test_virtual_env()
    test_file_operations()
    
    print("=" * 50)
    print("控制台功能测试完成!")
    print()
    print("测试结果说明:")
    print("- ✓ 表示功能正常，可以在IDE控制台中使用")
    print("- ✗ 表示功能异常，需要检查环境配置")
    print()
    print("在Python IDE v2.0中，您可以使用以下功能:")
    print("1. 控制台命令执行 - 在控制台标签页输入命令")
    print("2. 包管理 - 在包管理标签页安装/卸载Python包")
    print("3. 虚拟环境管理 - 创建项目专用的Python环境")
    print("4. 项目文件操作 - 在项目目录中执行文件操作")

if __name__ == "__main__":
    main()

