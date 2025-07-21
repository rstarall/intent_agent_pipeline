#!/usr/bin/env python3
"""
依赖安装脚本

自动安装项目所需的所有依赖包，并处理可能的安装问题。
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd: str) -> tuple[int, str, str]:
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "命令执行超时"
    except Exception as e:
        return 1, "", str(e)


def check_python_version():
    """检查Python版本"""
    print("🐍 检查Python版本...")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print(f"❌ Python版本过低: {version.major}.{version.minor}")
        print("请安装Python 3.11或更高版本")
        return False
    
    print(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
    return True


def install_requirements():
    """安装requirements.txt中的依赖"""
    print("📦 安装基础依赖...")
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    requirements_file = project_root / "requirements.txt"
    
    if not requirements_file.exists():
        print("❌ requirements.txt文件不存在")
        return False
    
    # 升级pip
    print("⬆️ 升级pip...")
    returncode, stdout, stderr = run_command(f"{sys.executable} -m pip install --upgrade pip")
    if returncode != 0:
        print(f"⚠️ pip升级失败: {stderr}")
    
    # 安装依赖
    cmd = f"{sys.executable} -m pip install -r {requirements_file}"
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        print("✅ 基础依赖安装完成")
        return True
    else:
        print(f"❌ 基础依赖安装失败: {stderr}")
        return False


def install_dev_requirements():
    """安装开发依赖"""
    print("🛠️ 安装开发依赖...")
    
    project_root = Path(__file__).parent.parent
    dev_requirements_file = project_root / "requirements-dev.txt"
    
    if not dev_requirements_file.exists():
        print("⚠️ requirements-dev.txt文件不存在，跳过开发依赖安装")
        return True
    
    cmd = f"{sys.executable} -m pip install -r {dev_requirements_file}"
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        print("✅ 开发依赖安装完成")
        return True
    else:
        print(f"❌ 开发依赖安装失败: {stderr}")
        return False


def install_optional_packages():
    """安装可选包"""
    print("🔧 安装可选包...")
    
    optional_packages = [
        "uvloop",           # 高性能事件循环（Linux/Mac）
    ]
    
    success_count = 0
    
    for package in optional_packages:
        print(f"📦 尝试安装 {package}...")
        cmd = f"{sys.executable} -m pip install {package}"
        returncode, stdout, stderr = run_command(cmd)
        
        if returncode == 0:
            print(f"✅ {package} 安装成功")
            success_count += 1
        else:
            print(f"⚠️ {package} 安装失败（可选包）: {stderr}")
    
    print(f"📊 可选包安装完成: {success_count}/{len(optional_packages)}")
    return True


def verify_installation():
    """验证安装"""
    print("🔍 验证安装...")
    
    required_packages = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "redis",
        "structlog",
        "aiohttp",
        "httpx",
    ]
    
    failed_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            failed_packages.append(package)
    
    if failed_packages:
        print(f"\n❌ 以下包导入失败: {', '.join(failed_packages)}")
        print("请手动安装这些包或检查安装错误")
        return False
    else:
        print("\n🎉 所有核心包验证通过！")
        return True


def main():
    """主函数"""
    print("🚀 开始安装项目依赖...")
    print("=" * 50)
    
    success = True
    
    # 检查Python版本
    if not check_python_version():
        sys.exit(1)
    
    # 安装基础依赖
    if not install_requirements():
        success = False
    
    # 安装开发依赖
    if not install_dev_requirements():
        success = False
    
    # 安装可选包
    install_optional_packages()
    
    # 验证安装
    if not verify_installation():
        success = False
    
    print("=" * 50)
    
    if success:
        print("🎉 依赖安装完成！")
        print("\n下一步:")
        print("1. 复制 .env.example 到 .env")
        print("2. 编辑 .env 文件，填入相应的API密钥")
        print("3. 运行 python -m uvicorn app.main:app --reload")
        sys.exit(0)
    else:
        print("💥 依赖安装过程中出现错误！")
        print("请检查错误信息并手动解决")
        sys.exit(1)


if __name__ == "__main__":
    main()
