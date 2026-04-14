#!/usr/bin/env python
"""
PyLinkAgent 快速启动脚本

用法:
    python scripts/quickstart_agent.py

环境变量:
    MANAGEMENT_URL - 控制台地址 (默认：http://localhost:9999)
    APP_NAME - 应用名称 (默认：my-app)
    AGENT_ID - Agent ID (默认：pylinkagent-{pid})
    REGISTER_NAME - 注册中心类型 (默认：zookeeper)
    ZK_ENABLED - 是否启用 ZK (默认：true)
"""

import os
import sys
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置环境变量 (可以在运行前设置)
os.environ.setdefault('MANAGEMENT_URL', 'http://localhost:9999')
os.environ.setdefault('APP_NAME', 'my-app')
os.environ.setdefault('AGENT_ID', f'pylinkagent-{os.getpid()}')
os.environ.setdefault('REGISTER_NAME', 'zookeeper')
os.environ.setdefault('ZK_ENABLED', 'true')
os.environ.setdefault('SIMULATOR_ENV_CODE', 'test')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """主函数"""
    print("=" * 60)
    print("PyLinkAgent 快速启动")
    print("=" * 60)
    print(f"控制台地址：{os.environ.get('MANAGEMENT_URL')}")
    print(f"应用名称：{os.environ.get('APP_NAME')}")
    print(f"Agent ID: {os.environ.get('AGENT_ID')}")
    print(f"注册中心：{os.environ.get('REGISTER_NAME')}")
    print(f"ZK 启用：{os.environ.get('ZK_ENABLED')}")
    print("=" * 60)

    # 导入并启动
    from pylinkagent import bootstrap, shutdown

    try:
        bootstrapper = bootstrap()

        if bootstrapper:
            print("\n✓ PyLinkAgent 启动成功")
            print("按 Ctrl+C 停止运行...\n")

            # 等待关闭
            bootstrapper.wait()
        else:
            print("\n✗ PyLinkAgent 启动失败")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n收到中断信号，正在关闭...")
        shutdown()
        print("已关闭")
    except Exception as e:
        print(f"\n✗ 运行时错误：{e}")
        import traceback
        traceback.print_exc()
        shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
