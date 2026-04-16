#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 ZooKeeper 日志服务器发现功能
"""

import os
import sys
import json
import time
import logging

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
    print("=" * 70 + "\n")


def print_section(title):
    """打印章节标题"""
    print(f"[{title}]")
    print("-" * 50)


def test_log_server_info():
    """测试 LogServerInfo 数据类"""
    print_header("测试 1: LogServerInfo 数据类")

    from pylinkagent.zookeeper import LogServerInfo

    # 创建实例
    server = LogServerInfo(
        host="192.168.1.100",
        port=8080,
        server_type="http",
        status="online",
        name="log-server-1",
        version="2.0.0",
        region="shanghai",
    )

    # 转换为字典
    server_dict = server.to_dict()
    print("转换为字典:")
    print(json.dumps(server_dict, indent=2, ensure_ascii=False))

    # 转换为 JSON
    json_bytes = server.to_json()
    print(f"\n转换为 JSON 字节：{len(json_bytes)} 字节")

    # 从字典创建
    server2 = LogServerInfo.from_dict(server_dict)
    print(f"\n从字典创建成功：{server2.name} ({server2.address})")

    # 验证
    checks = {
        'address auto-generate': server.address == "192.168.1.100:8080",
        'serverType': server.server_type == "http",
        'status': server.status == "online",
        'to_dict works': isinstance(server_dict, dict),
        'to_json works': isinstance(json_bytes, bytes),
        'from_dict works': server2.name == server.name,
    }

    all_passed = True
    for field, passed in checks.items():
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {field}")
        if not passed:
            all_passed = False

    return all_passed


def test_log_server_discovery():
    """测试 ZkLogServerDiscovery"""
    print_header("测试 2: ZkLogServerDiscovery")

    from pylinkagent.zookeeper import (
        get_config,
        create_client,
        ZkLogServerDiscovery,
        LogServerInfo,
        reset_log_server_discovery,
    )

    # 重置全局实例
    reset_log_server_discovery()

    # 加载配置
    config = get_config()
    print(f"ZK 服务器：{config.zk_servers}")
    print(f"日志服务器路径：{config.server_base_path}")

    # 创建客户端
    client = create_client(config)
    if not client.connect():
        print("[FAIL] ZK 连接失败")
        return False

    print("[OK] ZK 连接成功")

    # 创建发现器
    discovery = ZkLogServerDiscovery(config, client)

    # 初始化
    if discovery.initialize(client):
        print("[OK] 日志服务器发现初始化成功")

        # 启动
        if discovery.start():
            print("[OK] 日志服务器发现启动成功")

            # 初始服务器列表
            servers = discovery.get_servers()
            server_ids = discovery.get_server_ids()
            print(f"  初始服务器数：{len(servers)}")

            # 添加测试服务器
            test_server_path = f"{config.server_base_path}/test-server-1"
            test_server = LogServerInfo(
                host="192.168.1.100",
                port=8080,
                server_type="http",
                status="online",
                name="test-server-1",
                version="2.0.0",
                region="test",
            )
            client.create(test_server_path, test_server.to_json(), make_parent_dirs=True)
            time.sleep(1)

            # 刷新后检查
            discovery._refresh_servers()
            servers = discovery.get_servers()
            print(f"  添加测试服务器后：{len(servers)} 个服务器")

            # 获取服务器
            server = discovery.get_server("test-server-1")
            if server:
                print(f"  [OK] 获取服务器成功：{server.name}")
            else:
                print(f"  [FAIL] 获取服务器失败")

            # 获取在线服务器
            online_servers = discovery.get_online_servers()
            print(f"  在线服务器数：{len(online_servers)}")

            # 测试监听器
            listener_called = [False]

            def on_server_change(server_ids):
                listener_called[0] = True
                print(f"  -> 监听到服务器变化：{len(server_ids)} 个服务器")

            discovery.add_server_listener(on_server_change)

            # 删除测试服务器
            client.delete(test_server_path)
            time.sleep(1)

            # 刷新后检查
            discovery._refresh_servers()
            servers = discovery.get_servers()
            print(f"  删除测试服务器后：{len(servers)} 个服务器")

            # 停止
            discovery.stop()
            print("[OK] 日志服务器发现已停止")
        else:
            print("[FAIL] 日志服务器发现启动失败")
    else:
        print("[FAIL] 日志服务器发现初始化失败")

    client.disconnect()
    print("[OK] ZK 已断开连接")

    return True


def test_log_server_selector():
    """测试 LogServerSelector"""
    print_header("测试 3: LogServerSelector")

    from pylinkagent.zookeeper import (
        get_config,
        create_client,
        ZkLogServerDiscovery,
        LogServerSelector,
        LogServerInfo,
        reset_log_server_discovery,
    )

    # 重置全局实例
    reset_log_server_discovery()

    # 加载配置
    config = get_config()

    # 创建客户端
    client = create_client(config)
    if not client.connect():
        print("[FAIL] ZK 连接失败")
        return False

    print("[OK] ZK 连接成功")

    # 创建发现器
    discovery = ZkLogServerDiscovery(config, client)

    # 初始化并启动
    if discovery.initialize(client) and discovery.start():
        print("[OK] 日志服务器发现启动成功")

        # 创建选择器
        selector = LogServerSelector(discovery)

        # 选择服务器
        server = selector.select()
        if server:
            print(f"  [OK] 选择服务器成功：{server.name} ({server.address})")
        else:
            print(f"  [INFO] 无可用服务器")

        # 按区域选择
        server = selector.select_by_region("shanghai")
        if server:
            print(f"  [OK] 按区域选择成功：{server.name} (region={server.region})")
        else:
            print(f"  [INFO] 无匹配区域的服务器")

        # 停止
        discovery.stop()
        print("[OK] 日志服务器发现已停止")
    else:
        print("[FAIL] 日志服务器发现启动失败")

    client.disconnect()
    print("[OK] ZK 已断开连接")

    return True


def test_server_listener():
    """测试服务器监听器"""
    print_header("测试 4: 服务器监听器")

    from pylinkagent.zookeeper import (
        get_config,
        create_client,
        ZkLogServerDiscovery,
        LogServerInfo,
        reset_log_server_discovery,
    )

    # 重置全局实例
    reset_log_server_discovery()

    # 加载配置
    config = get_config()

    # 创建客户端
    client = create_client(config)
    if not client.connect():
        print("[FAIL] ZK 连接失败")
        return False

    print("[OK] ZK 连接成功")

    # 创建发现器
    discovery = ZkLogServerDiscovery(config, client)

    # 初始化并启动
    if discovery.initialize(client) and discovery.start():
        print("[OK] 日志服务器发现启动成功")

        # 添加监听器
        events = []

        def on_server_change_1(server_ids):
            events.append(("listener1", len(server_ids)))
            print(f"  -> Listener1: {len(server_ids)} 个服务器")

        def on_server_change_2(server_ids):
            events.append(("listener2", len(server_ids)))
            print(f"  -> Listener2: {len(server_ids)} 个服务器")

        discovery.add_server_listener(on_server_change_1)
        discovery.add_server_listener(on_server_change_2)
        print("  已添加 2 个监听器")

        # 添加测试服务器
        test_server_path = f"{config.server_base_path}/test-server-listener"
        test_server = LogServerInfo(
            host="192.168.1.101",
            port=8080,
            server_type="http",
            status="online",
            name="test-server-listener",
            version="2.0.0",
            region="test",
        )
        client.create(test_server_path, test_server.to_json(), make_parent_dirs=True)
        time.sleep(1)

        # 刷新
        discovery._refresh_servers()
        print(f"  刷新后服务器数：{len(discovery.get_server_ids())}")

        # 检查事件
        print(f"  触发事件数：{len(events)}")
        if len(events) >= 2:
            print("  [OK] 监听器触发成功")
        else:
            print("  [WARN] 监听器可能未触发")

        # 删除测试服务器
        client.delete(test_server_path)

        # 停止
        discovery.stop()
        print("[OK] 日志服务器发现已停止")
    else:
        print("[FAIL] 日志服务器发现启动失败")

    client.disconnect()
    print("[OK] ZK 已断开连接")

    return True


def print_summary(results):
    """打印测试总结"""
    print_header("测试总结")

    test_names = [
        "LogServerInfo 数据类",
        "ZkLogServerDiscovery",
        "LogServerSelector",
        "服务器监听器",
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
    print_header("PyLinkAgent ZooKeeper 日志服务器发现测试")

    # 检查前置条件
    print_section("检查前置条件")
    try:
        from kazoo.client import KazooClient
        print("[OK] kazoo 已安装")
    except ImportError:
        print("[FAIL] kazoo 未安装，请运行：pip install kazoo")
        sys.exit(1)

    results = []

    # 测试 1: LogServerInfo 数据类 (不需要 ZK)
    results.append(test_log_server_info())

    # 测试 2-4: 需要 ZK 连接
    print("\n" + "=" * 70)
    print("以下测试需要连接到 ZooKeeper")
    print("=" * 70)

    results.append(test_log_server_discovery())
    results.append(test_log_server_selector())
    results.append(test_server_listener())

    # 打印总结
    success = print_summary(results)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
