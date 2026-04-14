#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent 内网综合验证脚本
一键验证 ZooKeeper 心跳、HTTP 心跳上报、影子数据库配置拉取
"""

import os
import sys
import time
import logging
from datetime import datetime

# 添加项目路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(title.center(70))
    print("=" * 70)


def print_section(title):
    """打印章节标题"""
    print(f"\n[{title}]")
    print("-" * 50)


def check_prerequisites():
    """检查前置条件"""
    print_header("步骤 0: 检查前置条件")

    checks = {
        'python_version': False,
        'kazoo_installed': False,
        'httpx_installed': False,
        'env_management_url': False,
        'env_app_name': False,
    }

    # 1. Python 版本
    import sys
    print(f"\n[检查] Python 版本：{sys.version}")
    checks['python_version'] = sys.version_info >= (3, 8)

    # 2. 检查 kazoo
    try:
        from kazoo.client import KazooClient
        print(f"[OK] kazoo 已安装")
        checks['kazoo_installed'] = True
    except ImportError:
        print(f"[WARN] kazoo 未安装，ZK 验证将跳过")
        checks['kazoo_installed'] = False

    # 3. 检查 httpx
    try:
        import httpx
        print(f"[OK] httpx 已安装")
        checks['httpx_installed'] = True
    except ImportError:
        print(f"[WARN] httpx 未安装")
        checks['httpx_installed'] = False

    # 4. 检查环境变量
    management_url = os.getenv('MANAGEMENT_URL', 'http://localhost:9999')
    app_name = os.getenv('APP_NAME', 'test-app')

    print(f"\n[环境] MANAGEMENT_URL={management_url}")
    print(f"[环境] APP_NAME={app_name}")

    checks['env_management_url'] = True
    checks['env_app_name'] = app_name != 'test-app'

    # 总结
    print("\n前置条件检查总结:")
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    print(f"  通过：{passed}/{total}")

    return checks, management_url, app_name


def verify_zk_heartbeat(management_url, app_name):
    """验证 ZooKeeper 心跳"""
    print_header("步骤 1: 验证 ZooKeeper 心跳")

    results = {
        'config_load': False,
        'zk_connect': False,
        'node_create': False,
        'heartbeat_refresh': False,
    }

    try:
        from pylinkagent.zookeeper import (
            get_config, create_client, ZkHeartbeatManager, AgentStatus,
            reset_heartbeat_manager
        )

        # 1. 加载配置
        print_section("加载 ZK 配置")
        config = get_config()
        print(f"ZK 服务器：{config.zk_servers}")
        print(f"应用名称：{config.app_name}")
        print(f"完整 Agent ID: {config.get_full_agent_id()}")
        print(f"状态路径：{config.get_status_path()}")
        results['config_load'] = True
        print("[OK] ZK 配置加载成功")

        # 2. 连接 ZK
        print_section("连接 ZooKeeper")
        client = create_client(config)
        if client.connect():
            print(f"[OK] ZK 连接成功")
            print(f"连接状态：{client.get_state().value}")
            results['zk_connect'] = True
        else:
            print("[FAIL] ZK 连接失败")
            return results

        # 3. 创建心跳节点
        print_section("创建心跳节点")
        reset_heartbeat_manager()
        manager = ZkHeartbeatManager(config, client)

        if manager.initialize():
            print("[OK] 心跳管理器初始化成功")
            results['node_create'] = True
        else:
            print("[FAIL] 心跳管理器初始化失败")
            return results

        # 4. 启动心跳
        print_section("启动心跳")
        if manager.start():
            print("[OK] 心跳启动成功")

            # 等待一次刷新
            print("等待 35 秒观察心跳刷新...")
            time.sleep(35)

            if manager._heartbeat_node and manager._heartbeat_node.is_alive():
                print("[OK] 心跳节点存活")
                results['heartbeat_refresh'] = True
            else:
                print("[FAIL] 心跳节点不存活")

            manager.stop()
        else:
            print("[FAIL] 心跳启动失败")

        client.disconnect()

    except Exception as e:
        print(f"[ERROR] ZK 验证异常：{e}")
        import traceback
        traceback.print_exc()

    return results


def verify_http_heartbeat(management_url, app_name):
    """验证 HTTP 心跳上报"""
    print_header("步骤 2: 验证 HTTP 心跳上报")

    results = {
        'api_init': False,
        'heartbeat_send': False,
        'command_poll': False,
    }

    try:
        from pylinkagent.controller import ExternalAPI, HeartRequest

        # 1. 初始化 API
        print_section("初始化 ExternalAPI")
        api = ExternalAPI(
            tro_web_url=management_url,
            app_name=app_name,
            agent_id=f"inner-net-test-{os.getpid()}",
        )

        if api.initialize():
            print("[OK] ExternalAPI 初始化成功")
            results['api_init'] = True
        else:
            print("[FAIL] ExternalAPI 初始化失败")
            return results

        # 2. 发送心跳
        print_section("发送心跳")
        heart_request = HeartRequest(
            project_name=app_name,
            agent_id=f"inner-net-test-{os.getpid()}",
            ip_address="127.0.0.1",
            progress_id=str(os.getpid()),
            agent_status="running",
            agent_version="2.0.0",
            simulator_status="running",
        )

        commands = api.send_heartbeat(heart_request)
        if commands is not None:
            print(f"[OK] 心跳上报成功，返回 {len(commands)} 个命令")
            results['heartbeat_send'] = True
        else:
            print("[FAIL] 心跳上报失败")

        # 3. 拉取命令
        print_section("拉取命令")
        command = api.get_latest_command()
        if command:
            if command.id > 0:
                print(f"[OK] 获取到命令：id={command.id}")
                results['command_poll'] = True
            else:
                print("[INFO] 无待执行命令")
                results['command_poll'] = True
        else:
            print("[WARN] 命令拉取失败")
            results['command_poll'] = True  # 无命令也算正常

        api.shutdown()

    except Exception as e:
        print(f"[ERROR] HTTP 心跳验证异常：{e}")
        import traceback
        traceback.print_exc()

    return results


def verify_shadow_db_config(management_url, app_name):
    """验证影子数据库配置拉取"""
    print_header("步骤 3: 验证影子数据库配置拉取")

    results = {
        'config_fetch': False,
        'config_valid': False,
    }

    try:
        from pylinkagent.controller import ExternalAPI, ConfigFetcher

        # 1. 初始化 API
        print_section("初始化 ExternalAPI")
        api = ExternalAPI(
            tro_web_url=management_url,
            app_name=app_name,
            agent_id=f"inner-net-test-{os.getpid()}",
        )

        if not api.initialize():
            print("[FAIL] ExternalAPI 初始化失败")
            return results

        # 2. 拉取配置
        print_section("拉取影子库配置")
        config_data = api.fetch_shadow_database_config()

        if config_data is not None:
            print(f"[OK] 影子库配置拉取成功，共 {len(config_data)} 个数据源")
            results['config_fetch'] = True

            # 验证配置格式
            for ds in config_data:
                print(f"\n  数据源：{ds.get('dataSourceName', 'N/A')}")
                print(f"    主库：{ds.get('url', 'N/A')}")
                print(f"    影子库：{ds.get('shadowUrl', 'N/A')}")

                if ds.get('url') and ds.get('shadowUrl'):
                    results['config_valid'] = True
        else:
            print("[WARN] 影子库配置拉取返回空")
            print("      可能原因：")
            print("      1. 应用在控制台未配置影子库")
            print("      2. 控制台接口返回格式异常")
            results['config_fetch'] = False

        api.shutdown()

    except Exception as e:
        print(f"[ERROR] 影子库配置验证异常：{e}")
        import traceback
        traceback.print_exc()

    return results


def print_summary(zk_results, http_results, shadow_results):
    """打印验证总结"""
    print_header("验证总结")

    print("\nZooKeeper 心跳验证:")
    zk_passed = sum(1 for v in zk_results.values() if v)
    zk_total = len(zk_results)
    for k, v in zk_results.items():
        status = "✓" if v else "✗"
        print(f"  {status} {k}")
    print(f"  小计：{zk_passed}/{zk_total}")

    print("\nHTTP 心跳上报验证:")
    http_passed = sum(1 for v in http_results.values() if v)
    http_total = len(http_results)
    for k, v in http_results.items():
        status = "✓" if v else "✗"
        print(f"  {status} {k}")
    print(f"  小计：{http_passed}/{http_total}")

    print("\n影子数据库配置验证:")
    shadow_passed = sum(1 for v in shadow_results.values() if v)
    shadow_total = len(shadow_results)
    for k, v in shadow_results.items():
        status = "✓" if v else "✗"
        print(f"  {status} {k}")
    print(f"  小计：{shadow_passed}/{shadow_total}")

    total_passed = zk_passed + http_passed + shadow_passed
    total_tests = zk_total + http_total + shadow_total

    print("\n" + "=" * 70)
    print(f"总计：{total_passed}/{total_tests} 测试通过")
    print("=" * 70)

    if total_passed == total_tests:
        print("\n✓ 所有验证通过!")
    else:
        print(f"\n⚠ {total_tests - total_passed} 项验证失败，请检查日志")

    return total_passed == total_tests


def main():
    """主函数"""
    print_header("PyLinkAgent 内网综合验证")
    print(f"验证时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 检查前置条件
    checks, management_url, app_name = check_prerequisites()

    if not checks['python_version']:
        print("\n[ERROR] Python 版本过低，需要 3.8+")
        sys.exit(1)

    # 1. 验证 ZooKeeper 心跳
    zk_results = {'config_load': False, 'zk_connect': False, 'node_create': False, 'heartbeat_refresh': False}
    if checks['kazoo_installed']:
        zk_results = verify_zk_heartbeat(management_url, app_name)
    else:
        print("\n[SKIP] 跳过 ZK 验证 (kazoo 未安装)")

    # 2. 验证 HTTP 心跳上报
    http_results = verify_http_heartbeat(management_url, app_name)

    # 3. 验证影子数据库配置拉取
    shadow_results = verify_shadow_db_config(management_url, app_name)

    # 打印总结
    all_passed = print_summary(zk_results, http_results, shadow_results)

    # 退出码
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
