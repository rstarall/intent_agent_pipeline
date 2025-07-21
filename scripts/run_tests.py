#!/usr/bin/env python3
"""
测试运行脚本

提供便捷的测试执行和报告功能。
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(command, cwd=None):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr


def run_unit_tests(verbose=False):
    """运行单元测试"""
    print("🧪 运行单元测试...")
    
    cmd = "python -m pytest tests/unit/ -m unit"
    if verbose:
        cmd += " -v"
    
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        print("✅ 单元测试通过")
    else:
        print("❌ 单元测试失败")
        print(stderr)
    
    return returncode == 0


def run_integration_tests(verbose=False):
    """运行集成测试"""
    print("🔗 运行集成测试...")
    
    cmd = "python -m pytest tests/integration/ -m integration"
    if verbose:
        cmd += " -v"
    
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        print("✅ 集成测试通过")
    else:
        print("❌ 集成测试失败")
        print(stderr)
    
    return returncode == 0


def run_all_tests(verbose=False):
    """运行所有测试"""
    print("🚀 运行所有测试...")
    
    cmd = "python -m pytest tests/"
    if verbose:
        cmd += " -v"
    
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        print("✅ 所有测试通过")
    else:
        print("❌ 部分测试失败")
        print(stderr)
    
    return returncode == 0


def run_coverage_tests():
    """运行覆盖率测试"""
    print("📊 运行覆盖率测试...")
    
    cmd = "python -m pytest tests/ --cov=app --cov-report=html --cov-report=term"
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        print("✅ 覆盖率测试完成")
        print("📈 覆盖率报告已生成到 htmlcov/ 目录")
    else:
        print("❌ 覆盖率测试失败")
        print(stderr)
    
    return returncode == 0


def run_fast_tests():
    """运行快速测试"""
    print("⚡ 运行快速测试...")
    
    cmd = "python -m pytest tests/ -m 'not slow'"
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        print("✅ 快速测试通过")
    else:
        print("❌ 快速测试失败")
        print(stderr)
    
    return returncode == 0


def run_slow_tests():
    """运行慢速测试"""
    print("🐌 运行慢速测试...")
    
    cmd = "python -m pytest tests/ -m slow"
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        print("✅ 慢速测试通过")
    else:
        print("❌ 慢速测试失败")
        print(stderr)
    
    return returncode == 0


def run_specific_test(test_path, verbose=False):
    """运行特定测试"""
    print(f"🎯 运行特定测试: {test_path}")
    
    cmd = f"python -m pytest {test_path}"
    if verbose:
        cmd += " -v"
    
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        print("✅ 测试通过")
    else:
        print("❌ 测试失败")
        print(stderr)
    
    return returncode == 0





def check_dependencies():
    """检查测试依赖"""
    print("📦 检查测试依赖...")
    
    required_packages = [
        "pytest",
        "pytest-asyncio", 
        "pytest-cov",
        "httpx"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        returncode, _, _ = run_command(f"python -c 'import {package.replace('-', '_')}'")
        if returncode != 0:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements-dev.txt")
        return False
    else:
        print("✅ 所有测试依赖已安装")
        return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="测试运行脚本")
    parser.add_argument("--unit", action="store_true", help="运行单元测试")
    parser.add_argument("--integration", action="store_true", help="运行集成测试")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    parser.add_argument("--coverage", action="store_true", help="运行覆盖率测试")
    parser.add_argument("--fast", action="store_true", help="运行快速测试")
    parser.add_argument("--slow", action="store_true", help="运行慢速测试")
    parser.add_argument("--test", type=str, help="运行特定测试文件或函数")
    parser.add_argument("--check-deps", action="store_true", help="检查测试依赖")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 切换到项目根目录
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    success = True
    
    if args.check_deps:
        success &= check_dependencies()
    

    
    if args.unit:
        success &= run_unit_tests(args.verbose)
    elif args.integration:
        success &= run_integration_tests(args.verbose)
    elif args.all:
        success &= run_all_tests(args.verbose)
    elif args.coverage:
        success &= run_coverage_tests()
    elif args.fast:
        success &= run_fast_tests()
    elif args.slow:
        success &= run_slow_tests()
    elif args.test:
        success &= run_specific_test(args.test, args.verbose)
    else:
        # 默认运行快速测试
        print("🔧 默认运行快速测试...")
        success &= check_dependencies()
        success &= run_fast_tests()
    
    if success:
        print("\n🎉 所有操作成功完成！")
        sys.exit(0)
    else:
        print("\n💥 部分操作失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
