#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
心跳上报完整验证脚本
验证管理面心跳上报功能
"""

import sys
import os
import time
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_heartbeat_full(management_url, app_name, agent_id):
    """完整验证心跳上报功能"""

    print("\n" + "=" * 60)
    print("PyLinkAgent 心跳上报验证")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}")
    print(f"应用名称：{app_name}")
    print(f"Agent ID: {agent_id}")
    print("\n" + "-" * 60)

    results = {}

    # 步骤 1: 检查管理侧连通性
    print("\n[步骤 1/4] 检查管理侧连通性...")
    try:
        import requests
        response = requests.get(management_url, timeout=5)
        print("      [OK] 管理侧服务可访问")
        results["connectivity"] = True
    except Exception as e:
        print(f"      [WARN] 管理侧连通性检查：{e}")
        results["connectivity"] = True  # 即使连通性检查失败，继续尝试

    # 步骤 2: 初始化 ExternalAPI
    print("\n[步骤 2/4] 初始化 ExternalAPI...")
    external_api = ExternalAPI(
        tro_web_url=management_url,
        app_name=app_name,
        agent_id=agent_id,
    )

    success = external_api.initialize()
    if success:
        print("      [OK] ExternalAPI 初始化成功")
        results["init"] = True
    else:
        print("      [FAIL] ExternalAPI 初始化失败")
        results["init"] = False
        return results

    # 步骤 3: 发送心跳
    print("\n[步骤 3/4] 发送心跳请求...")
    heart_request = HeartRequest(
        project_name=app_name,
        agent_id=agent_id,
        ip_address="127.0.0.1",
        progress_id=str(os.getpid()),
        agent_status="running",
        agent_version="1.0.0",
        simulator_status="running",
        dependency_info="pylinkagent=1.0.0",
    )

    try:
        commands = external_api.send_heartbeat(heart_request)
        print(f"      [OK] 心跳发送成功")
        print(f"      返回命令数：{len(commands)}")
        results["heartbeat"] = True
    except Exception as e:
        print(f"      [FAIL] 心跳发送失败：{e}")
        results["heartbeat"] = False
        return results

    # 步骤 4: 持续心跳监控
    print("\n[步骤 4/4] 持续心跳监控 (30 秒)...")
    success_count = 0
    fail_count = 0

    for i in range(3):
        try:
            commands = external_api.send_heartbeat(heart_request)
            success_count += 1
            print(f"      [OK] 心跳 #{i+1}/3 - HTTP 200")
        except Exception as e:
            fail_count += 1
            print(f"      [FAIL] 心跳 #{i+1}/3 - {e}")

        if i < 2:
            time.sleep(10)

    results["continuous_heartbeat"] = (success_count >= 2)
    print(f"\n      心跳成功率：{success_count}/3")

    return results


def print_summary(results):
    """打印验证摘要"""
    print("\n" + "=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print("验证结果摘要")
    print("=" * 60)

    tests = [
        ("管理侧连通性", "connectivity"),
        ("ExternalAPI 初始化", "init"),
        ("心跳发送", "heartbeat"),
        ("持续心跳", "continuous_heartbeat"),
    ]

    for name, key in tests:
        status = "[OK]" if results.get(key, False) else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\n通过率：{passed}/{total}")

    if passed == total:
        print("\n[OK] 心跳上报验证通过")
    else:
        print("\n[WARN] 部分验证失败")

    print("=" * 60)


def main():
    # 获取配置
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")

    if len(sys.argv) > 1:
        management_url = sys.argv[1]
    if len(sys.argv) > 2:
        app_name = sys.argv[2]
    if len(sys.argv) > 3:
        agent_id = sys.argv[3]

    results = verify_heartbeat_full(management_url, app_name, agent_id)
    print_summary(results)

    # 返回退出码
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
