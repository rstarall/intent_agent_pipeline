#!/usr/bin/env python3
"""
导入检查脚本

检查项目中所有重要模块的导入是否正常。
"""

import sys
import importlib
from typing import List, Tuple


def check_import(module_name: str, package_name: str = None) -> Tuple[bool, str]:
    """
    检查模块导入
    
    Args:
        module_name: 模块名
        package_name: 包名（用于显示）
        
    Returns:
        Tuple[bool, str]: (是否成功, 错误信息)
    """
    try:
        importlib.import_module(module_name)
        return True, ""
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return False, f"未知错误: {str(e)}"


def main():
    """主函数"""
    print("🔍 检查项目导入...")
    print("=" * 60)
    
    # 核心依赖
    core_packages = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("redis", "Redis"),
        ("aiohttp", "aiohttp"),
        ("httpx", "httpx"),
    ]
    
    # LangChain 相关
    langchain_packages = [
        ("langgraph", "LangGraph"),
        ("langchain", "LangChain"),
        ("langchain_openai", "LangChain OpenAI"),
        ("langchain_community", "LangChain Community"),
    ]
    
    # 数据处理
    data_packages = [
        ("pandas", "Pandas"),
        ("numpy", "NumPy"),
    ]
    
    # 日志和工具
    utility_packages = [
        ("structlog", "StructLog"),
        ("yaml", "PyYAML"),
        ("jinja2", "Jinja2"),
        ("dotenv", "python-dotenv"),
    ]
    
    # 可选包
    optional_packages = [
        ("pytest", "Pytest"),
    ]
    
    all_success = True
    
    def check_package_group(packages: List[Tuple[str, str]], group_name: str, required: bool = True):
        nonlocal all_success
        print(f"\n📦 {group_name}:")
        group_success = True
        
        for module_name, display_name in packages:
            success, error = check_import(module_name)
            if success:
                print(f"  ✅ {display_name}")
            else:
                print(f"  ❌ {display_name}: {error}")
                if required:
                    group_success = False
                    all_success = False
        
        if required and not group_success:
            print(f"  ⚠️ {group_name} 中有必需包导入失败")
        
        return group_success
    
    # 检查各组包
    check_package_group(core_packages, "核心框架", required=True)
    check_package_group(langchain_packages, "LangChain 生态", required=True)
    check_package_group(data_packages, "数据处理", required=True)
    check_package_group(utility_packages, "工具库", required=True)
    check_package_group(optional_packages, "可选包", required=False)
    
    print("\n" + "=" * 60)
    
    # 检查项目模块
    print("\n🏗️ 项目模块:")
    project_modules = [
        ("app.config.settings", "配置模块"),
        ("app.config.logging", "日志模块"),
        ("app.models", "数据模型"),
        ("app.core", "核心模块"),
    ]
    
    for module_name, display_name in project_modules:
        success, error = check_import(module_name)
        if success:
            print(f"  ✅ {display_name}")
        else:
            print(f"  ❌ {display_name}: {error}")
            all_success = False
    
    print("\n" + "=" * 60)
    
    if all_success:
        print("🎉 所有核心导入检查通过！")
        print("\n✨ 项目已准备就绪，可以运行：")
        print("   python -m uvicorn app.main:app --reload")
        return 0
    else:
        print("💥 部分导入检查失败！")
        print("\n🔧 解决方案：")
        print("1. 运行安装脚本: python scripts/install_deps.py")
        print("2. 手动安装缺失的包: pip install <package_name>")
        print("3. 查看详细安装指南: INSTALL.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
