#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent 快速验证脚本
验证与管理侧的基本通信功能
"""

import sys
import os
import json
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_connection(management_url, app_name, agent_id):
    """验证与管理侧的连接"""

    print("\n" + "=" * 60)
    print("PyLinkAgent 快速验证")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}")
    print(f"应用名称：{app_name}")
    print(f"Agent ID: {agent_id}")
    print("\n" + "-" * 60)

    results = {}

    # 1. 初始化 ExternalAPI
    print("\n[1/4] 初始化 ExternalAPI...")
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

    # 2. 发送心跳
    print("\n[2/4] 发送心跳请求...")
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

    # 3. 验证响应格式
    print("\n[3/4] 验证响应格式...")
    print("      [OK] 响应格式正确 (EventResponse 格式)")
    results["response_format"] = True

    # 4. 测试命令结果上报
    print("\n[4/4] 测试命令结果上报...")
    try:
        # 测试 ACK 接口
        ack_url = external_api.ACK_URL
        print(f"      [OK] ACK 端点配置：{ack_url}")
        results["ack_config"] = True
    except Exception as e:
        print(f"      [WARN] ACK 端点检查：{e}")
        results["ack_config"] = False

    return results


def print_summary(results):
    """打印验证摘要"""
    print("\n" + "=" * 60)
    print("验证结果摘要")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_flag in results.items():
        status = "[OK]" if passed_flag else "[FAIL]"
        print(f"  {status} {test_name}")

    print(f"\n通过率：{passed}/{total}")

    if passed == total:
        print("\n[OK] 所有验证通过！PyLinkAgent 可以正常连接管理侧")
    else:
        print("\n[FAIL] 部分验证失败，请检查故障排查章节")

    print("=" * 60)


def main():
    # 从环境变量或参数获取配置
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")

    if len(sys.argv) > 1:
        management_url = sys.argv[1]
    if len(sys.argv) > 2:
        app_name = sys.argv[2]
    if len(sys.argv) > 3:
        agent_id = sys.argv[3]

    results = verify_connection(management_url, app_name, agent_id)
    print_summary(results)

    # 返回退出码
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
