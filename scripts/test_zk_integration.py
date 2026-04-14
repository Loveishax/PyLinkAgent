"""
测试 ZooKeeper 集成

验证 PyLinkAgent 与 ZooKeeper 的连接和心跳功能
"""

import os
import sys
import time
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.zookeeper import (
    ZkConfig,
    ZkClient,
    ZkHeartbeatManager,
    AgentStatus,
    get_config,
    create_client,
    get_heartbeat_manager,
    reset_heartbeat_manager,
)
from pylinkagent.controller import (
    ZKIntegration,
    get_integration,
    reset_integration,
    initialize_zk,
    shutdown_zk,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_zk_config():
    """测试 ZK 配置加载"""
    print("\n=== 测试 ZK 配置加载 ===")

    config = get_config()
    print(f"ZK 服务器：{config.zk_servers}")
    print(f"应用名称：{config.app_name}")
    print(f"Agent ID: {config.agent_id}")
    print(f"完整 Agent ID: {config.get_full_agent_id()}")
    print(f"状态路径：{config.get_status_path()}")
    print(f"客户端路径：{config.get_client_path()}")

    assert config.zk_servers, "ZK 服务器地址不能为空"
    assert config.app_name, "应用名称不能为空"
    print("✓ ZK 配置加载成功")
    return config


def test_zk_client(config: ZkConfig):
    """测试 ZK 客户端连接"""
    print("\n=== 测试 ZK 客户端连接 ===")

    try:
        client = create_client(config)
        if client.connect():
            print(f"✓ ZK 连接成功：{config.zk_servers}")
            print(f"  连接状态：{client.get_state().value}")

            # 测试创建节点
            test_path = "/test/pylinkagent/connection_test"
            if client.ensure_path_exists("/test/pylinkagent"):
                print(f"✓ 父路径创建成功：/test/pylinkagent")

            if client.create(test_path, b'test_data', ephemeral=True):
                print(f"✓ 临时节点创建成功：{test_path}")

            # 测试获取数据
            data = client.get(test_path)
            if data == b'test_data':
                print(f"✓ 节点数据读取成功：{data}")

            # 测试删除节点
            if client.delete(test_path):
                print(f"✓ 节点删除成功：{test_path}")

            client.disconnect()
            print("✓ ZK 连接已断开")
            return True
        else:
            print("✗ ZK 连接失败")
            return False

    except Exception as e:
        print(f"✗ ZK 客户端测试失败：{e}")
        return False


def test_heartbeat_manager(config: ZkConfig):
    """测试心跳管理器"""
    print("\n=== 测试心跳管理器 ===")

    try:
        # 重置全局管理器
        reset_heartbeat_manager()

        manager = get_heartbeat_manager(config)

        # 初始化
        if not manager.initialize():
            print("✗ 心跳管理器初始化失败")
            return False
        print("✓ 心跳管理器初始化成功")

        # 设置 Simulator 信息
        manager.set_simulator_info(
            service="http://127.0.0.1:8080",
            port=8080,
            md5="test_md5_123456",
            jars=["middleware-1.0.jar", "pradar-1.0.jar"]
        )
        print("✓ Simulator 信息已设置")

        # 启动
        if not manager.start():
            print("✗ 心跳管理器启动失败")
            return False
        print("✓ 心跳管理器启动成功")

        # 更新状态
        manager.update_status(AgentStatus.RUNNING)
        print("✓ 状态更新为 RUNNING")

        # 等待心跳刷新
        print("等待 35 秒观察心跳刷新...")
        time.sleep(35)

        # 检查节点是否存活
        if manager._heartbeat_node and manager._heartbeat_node.is_alive():
            print("✓ 心跳节点存活")
        else:
            print("✗ 心跳节点不存活")

        # 停止
        manager.stop()
        print("✓ 心跳管理器已停止")

        return True

    except Exception as e:
        print(f"✗ 心跳管理器测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """测试完整的 ZK 集成"""
    print("\n=== 测试 ZK 完整集成 ===")

    try:
        # 重置集成
        reset_integration()

        # 初始化并启动
        if initialize_zk():
            print("✓ ZK 集成启动成功")

            integration = get_integration()

            # 检查状态
            if integration.is_running():
                print("✓ ZK 心跳运行中")
            else:
                print("✗ ZK 心跳未运行")

            # 设置 Simulator 信息
            integration.set_simulator_info(
                service="http://127.0.0.1:8080",
                port=8080
            )
            print("✓ Simulator 信息已设置")

            # 更新状态
            integration.update_status(AgentStatus.RUNNING)
            print("✓ 状态已更新")

            # 等待观察
            print("等待 10 秒观察...")
            time.sleep(10)

            # 关闭
            shutdown_zk()
            print("✓ ZK 集成已关闭")

            return True
        else:
            print("✗ ZK 集成启动失败 (可能 ZK 不可用)")
            return False

    except Exception as e:
        print(f"✗ ZK 集成测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("PyLinkAgent ZooKeeper 集成测试")
    print("=" * 60)

    # 设置测试环境
    os.environ['SIMULATOR_APP_NAME'] = 'test-pylinkagent-app'
    os.environ['SIMULATOR_AGENT_ID'] = 'test-agent-001'
    os.environ['SIMULATOR_ENV_CODE'] = 'test'

    # 1. 测试配置
    config = test_zk_config()

    # 2. 测试客户端连接
    if not test_zk_client(config):
        print("\n⚠ ZK 客户端连接失败，跳过后续测试")
        print("请确保 ZooKeeper 服务可用:")
        print(f"  地址：{config.zk_servers}")
        return

    # 3. 测试心跳管理器
    test_heartbeat_manager(config)

    # 4. 测试完整集成
    test_integration()

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
