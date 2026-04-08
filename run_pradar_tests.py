"""
PyLinkAgent Pradar 测试套件

运行所有 Pradar 相关测试
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("PyLinkAgent Pradar 测试套件")
    print("=" * 60)

    # 测试文件列表
    test_files = [
        "tests/test_trace_id.py",
        "tests/test_context.py",
        "tests/test_pradar.py",
        "tests/test_switcher.py",
        "tests/test_whitelist.py",
    ]

    # 运行测试
    exit_code = pytest.main(test_files + ["-v", "--tb=short"])

    print("\n" + "=" * 60)
    if exit_code == 0:
        print("所有测试通过！")
    else:
        print(f"测试失败，退出码：{exit_code}")
    print("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(run_all_tests())
