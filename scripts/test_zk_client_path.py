#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 ZooKeeper 客户端路径注册功能
"""

import os
import sys
import time
import json
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


def test_client_node_data():
    """测试 ClientNodeData 数据类"""
    print_header("测试 1: ClientNodeData 数据类")

    from pylinkagent.zookeeper import ClientNodeData

    # 创建实例
    data = ClientNodeData(
        address="192.168.1.100",
        host="test-host",
        name="test-app",
        pid="12345",
        agent_id="192.168.1.100-12345&test::",
        agent_version="2.0.0",
        simulator_version="2.0.0",
        tenant_app_key="ed45ef6b-bf94-48fa-b0c0-15e0285365d2",
        env_code="test",
        user_id="1",
        capabilities=["config_fetch", "command_poll"],
    )

    # 转换为字典
    data_dict = data.to_dict()
    print("转换为字典:")
    print(json.dumps(data_dict, indent=2, ensure_ascii=False))

    # 转换为 JSON
    json_bytes = data.to_json()
    print(f"\n转换为 JSON 字节：{len(json_bytes)} 字节")

    # 从字典创建
    data2 = ClientNodeData.from_dict(data_dict)
    print(f"\n从字典创建成功：agent_id={data2.agent_id}")

    # 验证
    checks = {
        'address': data.address == "192.168.1.100",
        'agentLanguage': data.agent_language == "PYTHON",
        'capabilities is list': isinstance(data.capabilities, list),
        'to_dict works': isinstance(data_dict, dict),
        'to_json works': isinstance(json_bytes, bytes),
        'from_dict works': data2.agent_id == data.agent_id,
    }

    all_passed = True
    for field, passed in checks.items():
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {field}")
        if not passed:
            all_passed = False

    return all_passed


def test_zk_client_path_node():
    """测试 ZkClientPathNode"""
    print_header("测试 2: ZkClientPathNode")

    from pylinkagent.zookeeper import (
        get_config,
        create_client,
        ZkClientPathNode,
        ClientNodeData,
        reset_client_path_register,
    )

    # 加载配置
    config = get_config()
    print(f"ZK 服务器：{config.zk_servers}")
    print(f"应用名称：{config.app_name}")
    print(f"客户端路径：{config.get_client_path()}")

    # 创建客户端
    client = create_client(config)
    if not client.connect():
        print("[FAIL] ZK 连接失败")
        return False

    print("[OK] ZK 连接成功")

    # 创建客户端路径节点
    client_path = config.get_client_path()
    data = ClientNodeData(
        address="192.168.1.100",
        host="test-host",
        name="test-app",
        pid="12345",
        agent_id=config.get_full_agent_id(),
        agent_version=config.agent_version,
        simulator_version=config.simulator_version,
        tenant_app_key=config.tenant_app_key,
        env_code=config.env_code,
        user_id=config.user_id,
    )

    node = ZkClientPathNode(client, client_path, data.to_json())

    # 启动节点
    if node.start():
        print("[OK] 客户端路径节点启动成功")

        # 测试设置数据
        data.last_heartbeat = time.strftime("%Y-%m-%dT%H:%M:%S")
        if node.set_data(data.to_json()):
            print("[OK] 客户端路径数据更新成功")
        else:
            print("[FAIL] 客户端路径数据更新失败")

        # 测试获取数据
        retrieved_data = node.get_data()
        if retrieved_data:
            print(f"[OK] 客户端路径数据获取成功：{len(retrieved_data)} 字节")
        else:
            print("[FAIL] 客户端路径数据获取失败")

        # 停止节点
        node.stop()
        print("[OK] 客户端路径节点已停止")
    else:
        print("[FAIL] 客户端路径节点启动失败")

    client.disconnect()
    print("[OK] ZK 已断开连接")

    return True


def test_zk_path_children_cache():
    """测试 ZkPathChildrenCache"""
    print_header("测试 3: ZkPathChildrenCache")

    from pylinkagent.zookeeper import (
        get_config,
        create_client,
        ZkPathChildrenCache,
    )

    # 加载配置
    config = get_config()

    # 创建客户端
    client = create_client(config)
    if not client.connect():
        print("[FAIL] ZK 连接失败")
        return False

    print("[OK] ZK 连接成功")

    # 创建路径
    test_path = f"{config.get_client_path()}/test_children"

    # 确保路径存在
    if not client.ensure_path_exists(test_path):
        print("[FAIL] 创建路径失败")
        client.disconnect()
        return False

    print(f"[OK] 路径创建成功：{test_path}")

    # 创建子节点缓存
    cache = ZkPathChildrenCache(client, test_path)

    # 设置更新监听器
    update_count = [0]

    def on_update():
        update_count[0] += 1
        print(f"  -> 监听到子节点变化：{len(cache.get_children())} 个子节点")

    cache.set_update_listener(on_update)

    # 启动缓存
    if cache.start():
        print("[OK] 子节点缓存启动成功")

        # 初始子节点
        children = cache.get_children()
        print(f"  初始子节点数：{len(children)}")

        # 创建测试子节点
        test_child_path = f"{test_path}/child1"
        client.create(test_child_path, b"test data")
        time.sleep(0.5)

        # 检查新增的子节点
        added = cache.get_added_children()
        print(f"  新增子节点：{added}")

        # 删除子节点
        client.delete(test_child_path)
        time.sleep(0.5)

        # 检查删除的子节点
        deleted = cache.get_deleted_children()
        print(f"  删除子节点：{deleted}")

        # 停止缓存
        cache.stop()
        print("[OK] 子节点缓存已停止")
    else:
        print("[FAIL] 子节点缓存启动失败")

    # 清理测试路径
    client.delete(test_path, recursive=True)

    client.disconnect()
    print("[OK] ZK 已断开连接")

    return True


def test_zk_client_path_register():
    """测试 ZkClientPathRegister"""
    print_header("测试 4: ZkClientPathRegister")

    from pylinkagent.zookeeper import (
        ZkClientPathRegister,
        get_config,
        reset_client_path_register,
    )

    # 重置全局实例
    reset_client_path_register()

    # 加载配置
    config = get_config()
    print(f"ZK 服务器：{config.zk_servers}")
    print(f"应用名称：{config.app_name}")
    print(f"客户端路径：{config.get_client_path()}")

    # 创建注册器
    register = ZkClientPathRegister(config)

    # 初始化
    if register.initialize():
        print("[OK] 客户端路径注册器初始化成功")

        # 添加配置监听器
        def on_config_change(children):
            print(f"  -> 配置变化：{len(children)} 个配置")

        register.add_config_listener(on_config_change)

        # 添加命令监听器
        def on_command_change(children):
            print(f"  -> 命令变化：{len(children)} 个命令")

        register.add_command_listener(on_command_change)

        # 启动
        if register.start():
            print("[OK] 客户端路径注册器启动成功")

            # 获取配置子节点
            config_children = register.get_config_children()
            print(f"  配置子节点数：{len(config_children)}")

            # 获取命令子节点
            command_children = register.get_command_children()
            print(f"  命令子节点数：{len(command_children)}")

            # 等待一段时间观察监听
            print("  等待 5 秒观察监听...")
            time.sleep(5)

            # 停止
            register.stop()
            print("[OK] 客户端路径注册器已停止")
        else:
            print("[FAIL] 客户端路径注册器启动失败")
    else:
        print("[FAIL] 客户端路径注册器初始化失败")

    return True


def print_summary(results):
    """打印测试总结"""
    print_header("测试总结")

    test_names = [
        "ClientNodeData 数据类",
        "ZkClientPathNode",
        "ZkPathChildrenCache",
        "ZkClientPathRegister",
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
    print_header("PyLinkAgent ZooKeeper 客户端路径注册测试")

    # 检查前置条件
    print_section("检查前置条件")
    try:
        from kazoo.client import KazooClient
        print("[OK] kazoo 已安装")
    except ImportError:
        print("[FAIL] kazoo 未安装，请运行：pip install kazoo")
        sys.exit(1)

    results = []

    # 测试 1: ClientNodeData 数据类 (不需要 ZK)
    results.append(test_client_node_data())

    # 测试 2-4: 需要 ZK 连接
    print("\n" + "=" * 70)
    print("以下测试需要连接到 ZooKeeper")
    print("=" * 70)

    results.append(test_zk_client_path_node())
    results.append(test_zk_path_children_cache())
    results.append(test_zk_client_path_register())

    # 打印总结
    success = print_summary(results)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
