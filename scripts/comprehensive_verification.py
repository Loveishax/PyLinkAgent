#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent 综合验证脚本
一键验证 ZooKeeper 心跳、客户端注册、影子配置拉取功能
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Any

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


# ==================== 打印工具 ====================

def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(title.center(70))
    print("=" * 70)


def print_section(title):
    """打印章节标题"""
    print(f"\n[{title}]")
    print("-" * 50)


def print_result(name, passed, detail=""):
    """打印测试结果"""
    status = "OK" if passed else "FAIL"
    if detail:
        print(f"  [{status}] {name}: {detail}")
    else:
        print(f"  [{status}] {name}")


# ==================== 前置检查 ====================

def check_prerequisites() -> Dict[str, bool]:
    """检查前置条件"""
    print_header("步骤 0: 检查前置条件")

    checks = {}

    # 1. Python 版本
    print(f"\n[检查] Python 版本：{sys.version}")
    checks['python_version'] = sys.version_info >= (3, 8)
    print_result("Python >= 3.8", checks['python_version'], sys.version.split()[0])

    # 2. 检查 kazoo
    try:
        from kazoo.client import KazooClient
        checks['kazoo_installed'] = True
        print_result("kazoo 已安装", True)
    except ImportError:
        checks['kazoo_installed'] = False
        print_result("kazoo 已安装", False, "请运行：pip install kazoo")

    # 3. 检查 httpx
    try:
        import httpx
        checks['httpx_installed'] = True
        print_result("httpx 已安装", True)
    except ImportError:
        checks['httpx_installed'] = False
        print_result("httpx 已安装", False, "可选，用于 HTTP 请求")

    # 4. 检查环境变量
    print("\n[检查] 环境变量:")
    env_vars = {
        'SIMULATOR_ZK_SERVERS': 'ZK 服务器地址',
        'SIMULATOR_APP_NAME': '应用名称',
        'SIMULATOR_AGENT_ID': 'Agent ID',
        'SIMULATOR_ENV_CODE': '环境代码',
        'SIMULATOR_USER_ID': '用户 ID',
        'SIMULATOR_TENANT_APP_KEY': '租户 AppKey',
        'MANAGEMENT_URL': '控制台地址',
    }

    checks['env_configured'] = True
    for env_name, desc in env_vars.items():
        value = os.environ.get(env_name, '未设置')
        status = "✓" if value != '未设置' else "○"
        print(f"  {status} {env_name} = {value}")
        if env_name in ['SIMULATOR_ZK_SERVERS', 'SIMULATOR_APP_NAME']:
            if value == '未设置':
                checks['env_configured'] = False

    # 总结
    print("\n前置条件检查总结:")
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    print(f"  通过：{passed}/{total}")

    return checks


# ==================== 验证 1: ZooKeeper 心跳 ====================

def verify_zk_heartbeat() -> Dict[str, bool]:
    """验证 ZooKeeper 心跳"""
    print_header("验证 1: ZooKeeper 心跳")

    results = {
        'config_load': False,
        'zk_connect': False,
        'node_create': False,
        'heartbeat_refresh': False,
    }

    try:
        from pylinkagent.zookeeper import (
            get_config,
            create_client,
            ZkHeartbeatManager,
            AgentStatus,
            reset_heartbeat_manager,
        )

        # 1. 加载配置
        print_section("加载 ZK 配置")
        config = get_config()
        print(f"  ZK 服务器：{config.zk_servers}")
        print(f"  应用名称：{config.app_name}")
        print(f"  完整 Agent ID: {config.get_full_agent_id()}")
        print(f"  状态路径：{config.get_status_path()}")
        results['config_load'] = True
        print_result("配置加载成功", True)

        # 2. 连接 ZK
        print_section("连接 ZooKeeper")
        client = create_client(config)
        if client.connect():
            print(f"  连接状态：{client.get_state().value}")
            print_result("ZK 连接成功", True)
            results['zk_connect'] = True
        else:
            print_result("ZK 连接成功", False)
            return results

        # 3. 创建心跳节点
        print_section("创建心跳节点")
        reset_heartbeat_manager()
        manager = ZkHeartbeatManager(config, client)

        if manager.initialize():
            print_result("心跳管理器初始化成功", True)
            results['node_create'] = True
        else:
            print_result("心跳管理器初始化成功", False)
            return results

        # 4. 启动心跳
        print_section("启动心跳")
        if manager.start():
            print_result("心跳启动成功", True)

            # 等待一次刷新
            print("  等待 35 秒观察心跳刷新...")
            time.sleep(35)

            if manager._heartbeat_node and manager._heartbeat_node.is_alive():
                print_result("心跳节点存活", True)
                results['heartbeat_refresh'] = True

                # 验证节点数据
                data = manager._heartbeat_node.get_data()
                if data:
                    heartbeat_data = json.loads(data.decode('utf-8'))
                    print(f"  心跳数据：agentStatus={heartbeat_data.get('agentStatus')}")
                    print(f"  心跳数据：agentId={heartbeat_data.get('agentId')}")
            else:
                print_result("心跳节点存活", False)

            manager.stop()
        else:
            print_result("心跳启动成功", False)

        client.disconnect()
        print_result("ZK 已断开连接", True)

    except Exception as e:
        print_result("验证异常", False, str(e))
        import traceback
        traceback.print_exc()

    return results


# ==================== 验证 2: 客户端路径注册 ====================

def verify_client_path_register() -> Dict[str, bool]:
    """验证客户端路径注册"""
    print_header("验证 2: 客户端路径注册")

    results = {
        'config_load': False,
        'zk_connect': False,
        'client_node_create': False,
        'config_cache_start': False,
        'command_cache_start': False,
    }

    try:
        from pylinkagent.zookeeper import (
            get_config,
            create_client,
            ZkClientPathRegister,
            ClientNodeData,
            reset_client_path_register,
        )

        # 1. 加载配置
        print_section("加载 ZK 配置")
        config = get_config()
        print(f"  ZK 服务器：{config.zk_servers}")
        print(f"  应用名称：{config.app_name}")
        print(f"  客户端路径：{config.get_client_path()}")
        results['config_load'] = True
        print_result("配置加载成功", True)

        # 2. 连接 ZK
        print_section("连接 ZooKeeper")
        client = create_client(config)
        if client.connect():
            print(f"  连接状态：{client.get_state().value}")
            print_result("ZK 连接成功", True)
            results['zk_connect'] = True
        else:
            print_result("ZK 连接成功", False)
            return results

        # 3. 创建客户端路径注册器
        print_section("创建客户端路径注册器")
        reset_client_path_register()
        register = ZkClientPathRegister(config, client)

        if register.initialize():
            print_result("客户端路径注册器初始化成功", True)
            results['client_node_create'] = True
        else:
            print_result("客户端路径注册器初始化成功", False)
            return results

        # 4. 启动注册器
        print_section("启动客户端路径注册")
        if register.start():
            print_result("客户端路径注册器启动成功", True)
            results['config_cache_start'] = True
            results['command_cache_start'] = True

            # 验证配置和命令缓存
            config_children = register.get_config_children()
            command_children = register.get_command_children()
            print(f"  配置子节点数：{len(config_children)}")
            print(f"  命令子节点数：{len(command_children)}")

            # 添加测试监听器
            listener_called = [False]

            def on_config_change(children):
                listener_called[0] = True
                print(f"  -> 配置变化监听到：{len(children)} 个配置")

            def on_command_change(children):
                listener_called[0] = True
                print(f"  -> 命令变化监听到：{len(children)} 个命令")

            register.add_config_listener(on_config_change)
            register.add_command_listener(on_command_change)
            print_result("监听器添加成功", True)

            # 等待一段时间观察监听
            print("  等待 5 秒观察监听...")
            time.sleep(5)

            # 停止
            register.stop()
            print_result("客户端路径注册器已停止", True)
        else:
            print_result("客户端路径注册器启动成功", False)

        client.disconnect()
        print_result("ZK 已断开连接", True)

    except Exception as e:
        print_result("验证异常", False, str(e))
        import traceback
        traceback.print_exc()

    return results


# ==================== 验证 3: 影子配置拉取 ====================

def verify_shadow_config_fetch() -> Dict[str, bool]:
    """验证影子配置拉取"""
    print_header("验证 3: 影子配置拉取")

    results = {
        'api_init': False,
        'shadow_db_fetch': False,
        'shadow_db_valid': False,
        'remote_call_fetch': False,
    }

    try:
        from pylinkagent.controller import ExternalAPI

        # 1. 初始化 API
        print_section("初始化 ExternalAPI")
        management_url = os.getenv('MANAGEMENT_URL', 'http://localhost:9999')
        app_name = os.getenv('APP_NAME', 'default-app')
        agent_id = os.getenv('AGENT_ID', f'test-agent-{os.getpid()}')

        print(f"  控制台地址：{management_url}")
        print(f"  应用名称：{app_name}")
        print(f"  Agent ID: {agent_id}")

        # 添加请求头
        extra_headers = {}
        user_app_key = os.getenv('USER_APP_KEY', '')
        if user_app_key:
            extra_headers['userAppKey'] = user_app_key
        tenant_app_key = os.getenv('TENANT_APP_KEY', '')
        if tenant_app_key:
            extra_headers['tenantAppKey'] = tenant_app_key
        user_id = os.getenv('USER_ID', '')
        if user_id:
            extra_headers['userId'] = user_id
        env_code = os.getenv('ENV_CODE', 'test')
        if env_code:
            extra_headers['envCode'] = env_code

        api = ExternalAPI(
            tro_web_url=management_url,
            app_name=app_name,
            agent_id=agent_id,
            extra_headers=extra_headers if extra_headers else None,
        )

        if api.initialize():
            print_result("ExternalAPI 初始化成功", True)
            results['api_init'] = True
        else:
            print_result("ExternalAPI 初始化成功", False)
            return results

        # 2. 拉取影子库配置
        print_section("拉取影子库配置")
        config_data = api.fetch_shadow_database_config()

        if config_data is not None:
            print_result("影子库配置拉取成功", True, f"{len(config_data)} 个数据源")
            results['shadow_db_fetch'] = True

            # 验证配置格式
            for ds in config_data[:3]:  # 只显示前 3 个
                print(f"  数据源：{ds.get('dataSourceName', 'N/A')}")
                print(f"    主库：{ds.get('url', 'N/A')}")
                print(f"    影子库：{ds.get('shadowUrl', 'N/A')}")

            if config_data and config_data[0].get('url') and config_data[0].get('shadowUrl'):
                results['shadow_db_valid'] = True
                print_result("配置格式验证", True)
        else:
            print_result("影子库配置拉取成功", False, "返回空或失败")
            print("  可能原因：")
            print("    1. 应用在控制台未配置影子库")
            print("    2. 控制台接口返回格式异常")
            print("    3. 网络连接问题")

        # 3. 拉取远程调用配置
        print_section("拉取远程调用配置")
        remote_config = api.fetch_remote_call_config()

        if remote_config is not None:
            print_result("远程调用配置拉取成功", True)
            results['remote_call_fetch'] = True

            # 显示配置摘要
            if 'newBlists' in remote_config:
                print(f"  黑名单：{len(remote_config.get('newBlists', []))} 条")
            if 'wLists' in remote_config:
                print(f"  白名单：{len(remote_config.get('wLists', []))} 条")
            if 'mockConfigs' in remote_config:
                print(f"  Mock 配置：{len(remote_config.get('mockConfigs', []))} 条")
        else:
            print_result("远程调用配置拉取成功", False, "返回空或失败")
            print("  可能原因：")
            print("    1. 应用在控制台未配置远程调用规则")
            print("    2. 控制台接口返回格式异常")

        api.shutdown()
        print_result("ExternalAPI 已关闭", True)

    except Exception as e:
        print_result("验证异常", False, str(e))
        import traceback
        traceback.print_exc()

    return results


# ==================== 验证总结 ====================

def print_summary(zk_results, client_results, shadow_results):
    """打印验证总结"""
    print_header("验证总结")

    print("\nZooKeeper 心跳验证:")
    zk_passed = sum(1 for v in zk_results.values() if v)
    zk_total = len(zk_results)
    for k, v in zk_results.items():
        status = "OK" if v else "FAIL"
        print(f"  [{status}] {k}")
    print(f"  小计：{zk_passed}/{zk_total}")

    print("\n客户端路径注册验证:")
    client_passed = sum(1 for v in client_results.values() if v)
    client_total = len(client_results)
    for k, v in client_results.items():
        status = "OK" if v else "FAIL"
        print(f"  [{status}] {k}")
    print(f"  小计：{client_passed}/{client_total}")

    print("\n影子配置拉取验证:")
    shadow_passed = sum(1 for v in shadow_results.values() if v)
    shadow_total = len(shadow_results)
    for k, v in shadow_results.items():
        status = "OK" if v else "FAIL"
        print(f"  [{status}] {k}")
    print(f"  小计：{shadow_passed}/{shadow_total}")

    total_passed = zk_passed + client_passed + shadow_passed
    total_tests = zk_total + client_total + shadow_total

    print("\n" + "=" * 70)
    print(f"总计：{total_passed}/{total_tests} 测试通过")
    print("=" * 70)

    if total_passed == total_tests:
        print("\n[SUCCESS] 所有验证通过!")
        return True
    else:
        print(f"\n[WARN] {total_tests - total_passed} 项验证失败，请检查日志")
        return False


# ==================== 主函数 ====================

def main():
    """主函数"""
    print_header("PyLinkAgent 综合验证")
    print(f"验证时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"验证项目：ZooKeeper 心跳、客户端路径注册、影子配置拉取")

    # 检查前置条件
    prereq_checks = check_prerequisites()

    if not prereq_checks.get('python_version', False):
        print("\n[ERROR] Python 版本过低，需要 3.8+")
        sys.exit(1)

    if not prereq_checks.get('kazoo_installed', False):
        print("\n[ERROR] kazoo 未安装，请运行：pip install kazoo")
        sys.exit(1)

    if not prereq_checks.get('env_configured', False):
        print("\n[WARN] 部分环境变量未配置，可能影响验证结果")
        print("       请确保设置 SIMULATOR_ZK_SERVERS 和 SIMULATOR_APP_NAME")

    # 1. 验证 ZooKeeper 心跳
    zk_results = verify_zk_heartbeat()

    # 2. 验证客户端路径注册
    client_results = verify_client_path_register()

    # 3. 验证影子配置拉取
    shadow_results = verify_shadow_config_fetch()

    # 打印总结
    all_passed = print_summary(zk_results, client_results, shadow_results)

    # 退出码
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
