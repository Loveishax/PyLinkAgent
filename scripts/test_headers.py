#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试请求头配置
验证环境变量和 extra_headers 参数是否正确配置
"""

import os
import sys
import json

# 添加项目路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

from pylinkagent.controller import ExternalAPI


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(title.center(70))
    print("=" * 70 + "\n")


def print_section(title):
    """打印章节标题"""
    print(f"[{title}]")
    print("-" * 50)


def test_headers_from_env():
    """测试从环境变量读取请求头"""
    print_header("测试 1: 从环境变量读取请求头")

    # 设置环境变量
    os.environ['USER_APP_KEY'] = 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2'
    os.environ['TENANT_APP_KEY'] = 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2'
    os.environ['USER_ID'] = '1'
    os.environ['ENV_CODE'] = 'test'

    api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="test-app",
        agent_id="test-agent",
    )

    headers = api._get_headers()

    print("环境变量配置:")
    print(f"  USER_APP_KEY={os.environ.get('USER_APP_KEY', 'N/A')}")
    print(f"  TENANT_APP_KEY={os.environ.get('TENANT_APP_KEY', 'N/A')}")
    print(f"  USER_ID={os.environ.get('USER_ID', 'N/A')}")
    print(f"  ENV_CODE={os.environ.get('ENV_CODE', 'N/A')}")

    print("\n生成的请求头:")
    for key, value in headers.items():
        print(f"  {key}: {value}")

    # 验证
    print("\n验证结果:")
    checks = {
        'userAppKey': headers.get('userAppKey') == 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2',
        'tenantAppKey': headers.get('tenantAppKey') == 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2',
        'userId': headers.get('userId') == '1',
        'envCode': headers.get('envCode') == 'test',
        'Content-Type': headers.get('Content-Type') == 'application/json',
    }

    all_passed = True
    for field, passed in checks.items():
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {field}")
        if not passed:
            all_passed = False

    return all_passed


def test_headers_from_parameter():
    """测试从 extra_headers 参数读取请求头"""
    print_header("测试 2: 从 extra_headers 参数读取请求头")

    # 清除环境变量
    for key in ['USER_APP_KEY', 'TENANT_APP_KEY', 'USER_ID', 'ENV_CODE']:
        if key in os.environ:
            del os.environ[key]

    api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="test-app",
        agent_id="test-agent",
        extra_headers={
            "userAppKey": "ed45ef6b-bf94-48fa-b0c0-15e0285365d2",
            "tenantAppKey": "ed45ef6b-bf94-48fa-b0c0-15e0285365d2",
            "userId": "1",
            "envCode": "test",
        }
    )

    headers = api._get_headers()

    print("extra_headers 参数配置:")
    print(json.dumps(api.extra_headers, indent=2, ensure_ascii=False))

    print("\n生成的请求头:")
    for key, value in headers.items():
        print(f"  {key}: {value}")

    # 验证
    print("\n验证结果:")
    checks = {
        'userAppKey': headers.get('userAppKey') == 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2',
        'tenantAppKey': headers.get('tenantAppKey') == 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2',
        'userId': headers.get('userId') == '1',
        'envCode': headers.get('envCode') == 'test',
        'Content-Type': headers.get('Content-Type') == 'application/json',
    }

    all_passed = True
    for field, passed in checks.items():
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {field}")
        if not passed:
            all_passed = False

    return all_passed


def test_headers_from_json_env():
    """测试从 JSON 环境变量读取请求头"""
    print_header("测试 3: 从 JSON 环境变量读取请求头")

    # 清除单个环境变量
    for key in ['USER_APP_KEY', 'TENANT_APP_KEY', 'USER_ID', 'ENV_CODE']:
        if key in os.environ:
            del os.environ[key]

    # 设置 JSON 格式环境变量
    os.environ['HTTP_MUST_HEADERS'] = json.dumps({
        "userAppKey": "ed45ef6b-bf94-48fa-b0c0-15e0285365d2",
        "tenantAppKey": "ed45ef6b-bf94-48fa-b0c0-15e0285365d2",
        "userId": "1",
        "envCode": "test",
    })

    api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="test-app",
        agent_id="test-agent",
    )

    headers = api._get_headers()

    print("HTTP_MUST_HEADERS 配置:")
    print(os.environ.get('HTTP_MUST_HEADERS', 'N/A'))

    print("\n生成的请求头:")
    for key, value in headers.items():
        print(f"  {key}: {value}")

    # 验证
    print("\n验证结果:")
    checks = {
        'userAppKey': headers.get('userAppKey') == 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2',
        'tenantAppKey': headers.get('tenantAppKey') == 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2',
        'userId': headers.get('userId') == '1',
        'envCode': headers.get('envCode') == 'test',
        'Content-Type': headers.get('Content-Type') == 'application/json',
    }

    all_passed = True
    for field, passed in checks.items():
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {field}")
        if not passed:
            all_passed = False

    # 清理
    del os.environ['HTTP_MUST_HEADERS']

    return all_passed


def test_headers_priority():
    """测试请求头优先级"""
    print_header("测试 4: 请求头优先级测试")

    # 同时设置多种配置
    os.environ['USER_APP_KEY'] = 'from-env-user-app-key'
    os.environ['TENANT_APP_KEY'] = 'from-env-tenant-app-key'
    os.environ['HTTP_MUST_HEADERS'] = json.dumps({
        "userAppKey": "from-json-user-app-key",
        "tenantAppKey": "from-json-tenant-app-key",
    })

    api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="test-app",
        agent_id="test-agent",
        extra_headers={
            "userAppKey": "from-parameter-user-app-key",
        }
    )

    headers = api._get_headers()

    print("配置:")
    print(f"  extra_headers: userAppKey=from-parameter-user-app-key")
    print(f"  USER_APP_KEY: from-env-user-app-key")
    print(f"  HTTP_MUST_HEADERS: userAppKey=from-json-user-app-key")

    print("\n生成的请求头:")
    for key, value in headers.items():
        print(f"  {key}: {value}")

    # 验证优先级：extra_headers > 单个环境变量 > JSON 环境变量
    print("\n优先级验证:")
    print(f"  userAppKey 应该来自 extra_headers: {headers.get('userAppKey')}")
    print(f"  tenantAppKey 应该来自环境变量：{headers.get('tenantAppKey')}")

    # 验证
    checks = {
        'userAppKey from parameter': headers.get('userAppKey') == 'from-parameter-user-app-key',
        'tenantAppKey from env': headers.get('tenantAppKey') == 'from-env-tenant-app-key',  # 环境变量优先于 JSON
    }

    all_passed = True
    for field, passed in checks.items():
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {field}")
        if not passed:
            all_passed = False

    # 清理
    for key in ['USER_APP_KEY', 'TENANT_APP_KEY', 'HTTP_MUST_HEADERS']:
        if key in os.environ:
            del os.environ[key]

    return all_passed


def test_default_headers():
    """测试默认请求头"""
    print_header("测试 5: 默认请求头测试")

    # 清除所有相关环境变量
    for key in ['USER_APP_KEY', 'TENANT_APP_KEY', 'USER_ID', 'ENV_CODE', 'HTTP_MUST_HEADERS']:
        if key in os.environ:
            del os.environ[key]

    api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="test-app",
        agent_id="test-agent",
    )

    headers = api._get_headers()

    print("环境变量配置：无")
    print("extra_headers 参数：无")

    print("\n生成的请求头:")
    for key, value in headers.items():
        print(f"  {key}: {value}")

    # 验证默认值
    print("\n默认值验证:")
    checks = {
        'Content-Type': headers.get('Content-Type') == 'application/json',
        'User-Agent': headers.get('User-Agent') == 'PyLinkAgent/1.0.0',
        'envCode default': headers.get('envCode') == 'test',  # 默认值
    }

    all_passed = True
    for field, passed in checks.items():
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {field}")
        if not passed:
            all_passed = False

    return all_passed


def print_summary(results):
    """打印测试总结"""
    print_header("测试总结")

    test_names = [
        "从环境变量读取请求头",
        "从 extra_headers 参数读取",
        "从 JSON 环境变量读取",
        "请求头优先级测试",
        "默认请求头测试",
    ]

    passed = sum(1 for r in results if r)
    total = len(results)

    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "OK" if result else "FAIL"
        print(f"  [{status}] 测试 {i+1}: {name}")

    print("\n" + "=" * 70)
    print(f"总计：{passed}/{total} 测试通过")
    print("=" * 70)

    if passed == total:
        print("\n所有测试通过!")
        return True
    else:
        print(f"\n{total - passed} 项测试失败!")
        return False


def main():
    """主函数"""
    print_header("PyLinkAgent 请求头配置测试")

    results = []

    # 测试 1: 从环境变量读取
    results.append(test_headers_from_env())

    # 测试 2: 从参数读取
    results.append(test_headers_from_parameter())

    # 测试 3: 从 JSON 环境变量读取
    results.append(test_headers_from_json_env())

    # 测试 4: 优先级测试
    results.append(test_headers_priority())

    # 测试 5: 默认值测试
    results.append(test_default_headers())

    # 打印总结
    success = print_summary(results)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
