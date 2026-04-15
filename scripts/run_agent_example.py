#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent 运行示例

展示如何配置请求头并启动 Agent
"""

import os
import sys

# 添加项目路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

from pylinkagent import bootstrap, shutdown

# ==================== 配置方式一：环境变量（推荐） ====================
# 在启动脚本中设置环境变量
# export USER_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
# export TENANT_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
# export USER_ID="1"
# export ENV_CODE="test"

# ==================== 配置方式二：代码中设置 ====================
# 在导入 bootstrap 之前设置环境变量
os.environ['USER_APP_KEY'] = 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2'
os.environ['TENANT_APP_KEY'] = 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2'
os.environ['USER_ID'] = '1'
os.environ['ENV_CODE'] = 'test'

# 其他配置
os.environ['MANAGEMENT_URL'] = 'http://localhost:9999'
os.environ['APP_NAME'] = 'default_demo'
os.environ['AGENT_ID'] = f'pylinkagent-{os.getpid()}'
os.environ['HEARTBEAT_INTERVAL'] = '60'
os.environ['AUTO_REGISTER_APP'] = 'true'

if __name__ == "__main__":
    print("=" * 70)
    print("PyLinkAgent 启动示例".center(70))
    print("=" * 70)

    print("\n配置信息:")
    print(f"  控制台地址：{os.environ.get('MANAGEMENT_URL')}")
    print(f"  应用名称：{os.environ.get('APP_NAME')}")
    print(f"  Agent ID: {os.environ.get('AGENT_ID')}")
    print(f"  用户 AppKey: {os.environ.get('USER_APP_KEY')}")
    print(f"  租户 AppKey: {os.environ.get('TENANT_APP_KEY')}")
    print(f"  用户 ID: {os.environ.get('USER_ID')}")
    print(f"  环境代码：{os.environ.get('ENV_CODE')}")

    print("\n启动 Agent...")
    print("-" * 70)

    try:
        # 启动 Agent
        bootstrapper = bootstrap()

        if bootstrapper and bootstrapper._is_running:
            print("\nAgent 启动成功！")
            print("按 Ctrl+C 停止...")

            # 等待关闭
            bootstrapper.wait()
        else:
            print("\nAgent 启动失败!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n收到中断信号")
    except Exception as e:
        print(f"\n启动异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # 关闭 Agent
        shutdown()
        print("\nAgent 已关闭")
