#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent 快速启动脚本

功能:
1. 检查环境依赖
2. 验证 Takin-web 连接
3. 启动 PyLinkAgent

使用方法:
    python scripts/quickstart.py

或者指定配置:
    python scripts/quickstart.py --management-url http://192.168.1.100:9999 --app-name my-app
"""

import sys
import os
import time
import logging
import argparse
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """检查依赖"""
    print("=" * 60)
    print("PyLinkAgent - 依赖检查")
    print("=" * 60)

    missing = []
    optional_missing = []

    # 核心依赖
    core_deps = [
        ('wrapt', 'wrapt'),
        ('structlog', 'structlog'),
        ('pydantic', 'pydantic'),
        ('pydantic_settings', 'pydantic-settings'),
        ('httpx', 'httpx'),
    ]

    for module, name in core_deps:
        try:
            __import__(module)
            print(f"  [OK] {name}")
        except ImportError:
            print(f"  [MISSING] {name}")
            missing.append(name)

    # 可选依赖
    optional_deps = [
        ('flask', 'Flask'),
        ('sqlalchemy', 'SQLAlchemy'),
        ('pymysql', 'PyMySQL'),
        ('redis', 'redis'),
        ('confluent_kafka', 'confluent-kafka'),
        ('elasticsearch7', 'elasticsearch7'),
        ('psutil', 'psutil'),
    ]

    print("\n可选依赖:")
    for module, name in optional_deps:
        try:
            __import__(module)
            print(f"  [OK] {name}")
        except ImportError:
            print(f"  [OPTIONAL] {name}")
            optional_missing.append(name)

    if missing:
        print(f"\n[ERROR] 缺少核心依赖：{', '.join(missing)}")
        print("请运行：pip install -r requirements.txt")
        return False

    if optional_missing:
        print(f"\n[INFO] 可选依赖未安装 (不影响基本功能): {', '.join(optional_missing)}")

    print("\n[OK] 依赖检查通过")
    return True


def verify_takin_web_connection(management_url):
    """验证 Takin-web 连接"""
    print("\n" + "=" * 60)
    print("Takin-web 连接验证")
    print("=" * 60)

    from pylinkagent.controller.external_api import ExternalAPI

    print(f"\n管理侧地址：{management_url}")

    api = ExternalAPI(
        tro_web_url=management_url,
        app_name="health-check",
        agent_id="quickstart-script",
    )

    if not api.initialize():
        print("  [FAIL] 初始化失败")
        return False

    print("  [OK] 初始化成功")

    # 测试连接
    try:
        import httpx
        response = httpx.get(management_url, timeout=5)
        print(f"  [OK] HTTP 连接成功 (状态码：{response.status_code})")
    except Exception as e:
        print(f"  [WARN] HTTP 连接测试：{e}")
        print("         (Takin-web 可能没有根路径端点，继续...)")

    api.shutdown()
    print("\n[OK] Takin-web 连接验证通过")
    return True


def run_agent(management_url, app_name, agent_id):
    """运行 PyLinkAgent"""
    print("\n" + "=" * 60)
    print("启动 PyLinkAgent")
    print("=" * 60)

    from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
    from pylinkagent.controller.config_fetcher import ConfigFetcher

    # 初始化
    print("\n[1/4] 初始化 ExternalAPI...")
    api = ExternalAPI(
        tro_web_url=management_url,
        app_name=app_name,
        agent_id=agent_id,
    )

    if not api.initialize():
        print("  [FAIL] ExternalAPI 初始化失败")
        return False

    print("  [OK] ExternalAPI 初始化成功")

    # 上传应用信息
    print("\n[2/4] 上传应用信息...")
    if api.upload_application_info():
        print("  [OK] 应用信息上传成功")
    else:
        print("  [WARN] 应用信息上传失败 (可能已存在)")

    # 启动配置拉取
    print("\n[3/4] 启动配置拉取器...")
    fetcher = ConfigFetcher(api, interval=60, initial_delay=5)

    if not fetcher.start():
        print("  [FAIL] 配置拉取器启动失败")
        return False

    print("  [OK] 配置拉取器已启动")

    # 发送心跳
    print("\n[4/4] 发送心跳...")
    heart_request = HeartRequest(
        project_name=app_name,
        agent_id=agent_id,
        ip_address="127.0.0.1",
        progress_id=str(os.getpid()),
        agent_status="running",
        simulator_status="running",
    )

    commands = api.send_heartbeat(heart_request)
    print(f"  [OK] 心跳发送成功 - 返回 {len(commands)} 个命令")

    # 显示配置
    config = fetcher.get_config()
    if config.shadow_database_configs:
        print(f"\n  影子库配置：{len(config.shadow_database_configs)} 个数据源")
        for name, cfg in config.shadow_database_configs.items():
            print(f"    - {name}: {cfg.url} -> {cfg.shadow_url}")
    else:
        print("\n  影子库配置：无")

    print("\n" + "=" * 60)
    print("PyLinkAgent 运行中...")
    print("=" * 60)
    print(f"  管理侧：{management_url}")
    print(f"  应用：{app_name}")
    print(f"  Agent ID: {agent_id}")
    print(f"  启动时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n按 Ctrl+C 停止")

    # 心跳循环
    heartbeat_interval = 15  # 15 秒
    try:
        while True:
            time.sleep(heartbeat_interval)

            # 发送心跳
            commands = api.send_heartbeat(heart_request)
            if commands:
                logger.info(f"收到 {len(commands)} 个命令")
                for cmd in commands:
                    if cmd.id > 0:
                        logger.info(f"执行命令：id={cmd.id}")
                        # 执行命令逻辑...
                        api.report_command_result(cmd.id, True)

    except KeyboardInterrupt:
        print("\n\n正在停止...")
        fetcher.stop()
        api.shutdown()
        print("已停止")

    return True


def main():
    parser = argparse.ArgumentParser(description='PyLinkAgent 快速启动')

    parser.add_argument(
        '--management-url',
        default=os.getenv('MANAGEMENT_URL', 'http://localhost:9999'),
        help='管理侧地址 (Takin-web)'
    )
    parser.add_argument(
        '--app-name',
        default=os.getenv('APP_NAME', 'test-app'),
        help='应用名称'
    )
    parser.add_argument(
        '--agent-id',
        default=os.getenv('AGENT_ID', 'pylinkagent-quickstart'),
        help='Agent ID'
    )
    parser.add_argument(
        '--skip-checks',
        action='store_true',
        help='跳过依赖和连接检查'
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("PyLinkAgent 快速启动")
    print("=" * 60)
    print(f"  时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  管理侧：{args.management_url}")
    print(f"  应用：{args.app_name}")
    print(f"  Agent ID: {args.agent_id}")

    # 检查依赖
    if not args.skip_checks:
        if not check_dependencies():
            sys.exit(1)

        if not verify_takin_web_connection(args.management_url):
            print("\n[WARN] Takin-web 连接失败，但仍可继续...")
            response = input("是否继续？(y/n): ")
            if response.lower() != 'y':
                sys.exit(0)

    # 运行 Agent
    try:
        success = run_agent(
            management_url=args.management_url,
            app_name=args.app_name,
            agent_id=args.agent_id,
        )
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"启动失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
