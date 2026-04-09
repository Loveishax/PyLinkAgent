#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
心跳持续监控脚本
持续发送心跳并监控响应
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


def run_heartbeat_monitor(management_url, app_name, agent_id, interval=10, count=6):
    """运行心跳监控"""

    print("\n" + "=" * 60)
    print("心跳持续监控")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}")
    print(f"应用名称：{app_name}")
    print(f"Agent ID: {agent_id}")
    print(f"心跳间隔：{interval} 秒")
    print(f"监控次数：{count}次")
    print("\n" + "-" * 60)

    # 初始化 ExternalAPI
    external_api = ExternalAPI(
        tro_web_url=management_url,
        app_name=app_name,
        agent_id=agent_id,
    )

    if not external_api.initialize():
        print("\n[ERROR] ExternalAPI 初始化失败")
        return False

    print("\n[INFO] 开始发送心跳...\n")

    success_count = 0
    fail_count = 0

    for i in range(count):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
            success_count += 1
            print(f"[{timestamp}] [OK] 心跳 #{i+1}/{count} - 返回 {len(commands)} 个命令")
        except Exception as e:
            fail_count += 1
            print(f"[{timestamp}] [FAIL] 心跳 #{i+1}/{count} - {e}")

        if i < count - 1:
            time.sleep(interval)

    # 打印摘要
    print("\n" + "-" * 60)
    print(f"\n心跳监控完成")
    print(f"  成功：{success_count}/{count}")
    print(f"  失败：{fail_count}/{count}")

    if success_count == count:
        print("\n[OK] 所有心跳发送成功！")
        return True
    else:
        print(f"\n[FAIL] {fail_count} 次心跳失败")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        management_url = sys.argv[1]
    else:
        management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")

    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")
    interval = int(os.getenv("HEARTBEAT_INTERVAL", "10"))
    count = int(os.getenv("HEARTBEAT_COUNT", "6"))

    success = run_heartbeat_monitor(management_url, app_name, agent_id, interval, count)
    sys.exit(0 if success else 1)
