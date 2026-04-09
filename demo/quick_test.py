"""
PyLinkAgent 快速测试脚本

用于快速验证与管理侧的连接
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest

def main():
    """快速测试"""

    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")

    print(f"管理侧地址：{management_url}")
    print(f"应用名称：{app_name}")
    print(f"Agent ID: {agent_id}")
    print("-" * 40)

    # 初始化
    api = ExternalAPI(
        tro_web_url=management_url,
        app_name=app_name,
        agent_id=agent_id,
    )

    print("初始化 ExternalAPI...")
    if api.initialize():
        print("[OK] 初始化成功")
    else:
        print("[FAIL] 初始化失败")
        return 1

    # 发送心跳
    print("发送心跳...")
    heart_req = HeartRequest(
        project_name=app_name,
        agent_id=agent_id,
        ip_address="127.0.0.1",
        progress_id=str(os.getpid()),
        agent_status="running",
        agent_version="1.0.0",
    )

    try:
        commands = api.send_heartbeat(heart_req)
        print(f"[OK] 心跳成功 - 返回 {len(commands)} 个命令")
        return 0
    except Exception as e:
        print(f"[FAIL] 心跳失败：{e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
