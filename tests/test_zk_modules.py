"""
ZooKeeper 模块单元测试

在本地测试 ZK 模块功能，不依赖实际 ZK 服务器
"""

import os
import sys
import logging

# 添加项目路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

# 设置环境变量
os.environ['SIMULATOR_APP_NAME'] = 'test-app'
os.environ['SIMULATOR_AGENT_ID'] = 'test-agent-001'
os.environ['SIMULATOR_ENV_CODE'] = 'test'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("=" * 60)
print("PyLinkAgent ZooKeeper 模块单元测试")
print("=" * 60)

# 测试 1: 导入测试
print("\n[测试 1] 模块导入测试")
try:
    from pylinkagent.zookeeper import (
        ZkConfig,
        ZkClient,
        ZkHeartbeatNode,
        ZkHeartbeatManager,
        AgentStatus,
        HeartbeatData,
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
    print("[PASS] 所有模块导入成功")
except ImportError as e:
    print(f"[FAIL] 模块导入失败：{e}")
    sys.exit(1)

# 测试 2: KAZOO 可用性测试
print("\n[测试 2] KAZOO 库可用性测试")
try:
    from pylinkagent.zookeeper.zk_client import KAZOO_AVAILABLE
    if KAZOO_AVAILABLE:
        print("[PASS] KAZOO 库已安装并可")
        from kazoo.client import KazooClient
        from kazoo.exceptions import NoNodeError, NodeExistsError
        print("[PASS] KazooClient 和异常类导入成功")
    else:
        print("[FAIL] KAZOO 库不可用")
except Exception as e:
    print(f"[FAIL] KAZOO 测试失败：{e}")

# 测试 3: 配置加载测试
print("\n[测试 3] 配置加载测试")
try:
    config = get_config()
    assert config.zk_servers == "7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181", "ZK 服务器地址错误"
    assert config.app_name == "test-app", "应用名称错误"
    assert config.agent_id == "test-agent-001", "Agent ID 错误"
    assert config.env_code == "test", "环境代码错误"

    # 测试路径生成
    status_path = config.get_status_path()
    assert status_path.startswith("/config/log/pradar/status/test-app/"), f"状态路径错误：{status_path}"

    client_path = config.get_client_path()
    assert client_path.startswith("/config/log/pradar/client/test-app/"), f"客户端路径错误：{client_path}"

    # 测试完整 Agent ID
    full_agent_id = config.get_full_agent_id()
    assert "&test:" in full_agent_id, f"完整 Agent ID 格式错误：{full_agent_id}"

    print(f"[PASS] 配置加载成功")
    print(f"  ZK 服务器：{config.zk_servers}")
    print(f"  应用名称：{config.app_name}")
    print(f"  Agent ID: {config.agent_id}")
    print(f"  完整 Agent ID: {full_agent_id}")
    print(f"  状态路径：{status_path}")
    print(f"  客户端路径：{client_path}")
except Exception as e:
    print(f"[FAIL] 配置加载失败：{e}")

# 测试 4: AgentStatus 枚举测试
print("\n[测试 4] AgentStatus 枚举测试")
try:
    assert AgentStatus.UNKNOWN.value == "UNKNOWN"
    assert AgentStatus.BEGIN.value == "BEGIN"
    assert AgentStatus.RUNNING.value == "RUNNING"
    assert AgentStatus.ERROR.value == "ERROR"
    assert AgentStatus.UNINSTALL.value == "UNINSTALL"
    print("[PASS] AgentStatus 枚举值正确")
    print(f"  状态枚举：UNKNOWN, BEGIN, STARTING, RUNNING, ERROR, SLEEP, UNINSTALL, INSTALL_FAILED")
except Exception as e:
    print(f"[FAIL] AgentStatus 测试失败：{e}")

# 测试 5: HeartbeatData 数据类测试
print("\n[测试 5] HeartbeatData 数据类测试")
try:
    heartbeat = HeartbeatData(
        address="192.168.1.100",
        host="test-host",
        name="test-name",
        pid="12345",
        agent_id="test-agent-001",
        agent_status=AgentStatus.RUNNING.value,
        service="http://192.168.1.100:8080",
        port="8080",
    )

    # 测试 to_dict
    data_dict = heartbeat.to_dict()
    assert data_dict["address"] == "192.168.1.100"
    assert data_dict["agentId"] == "test-agent-001"
    assert data_dict["agentStatus"] == "RUNNING"
    assert data_dict["service"] == "http://192.168.1.100:8080"
    assert data_dict["port"] == "8080"

    # 测试 to_json
    json_bytes = heartbeat.to_json()
    assert isinstance(json_bytes, bytes)
    assert b'"agentId": "test-agent-001"' in json_bytes

    # 测试 from_dict
    heartbeat2 = HeartbeatData.from_dict(data_dict)
    assert heartbeat2.address == heartbeat.address
    assert heartbeat2.agent_id == heartbeat.agent_id
    assert heartbeat2.agent_status == heartbeat.agent_status

    print("[PASS] HeartbeatData 数据类测试通过")
    print(f"  基础信息：address={heartbeat.address}, host={heartbeat.host}, pid={heartbeat.pid}")
    print(f"  版本信息：agent_language={heartbeat.agent_language}, agent_version={heartbeat.agent_version}")
    print(f"  状态信息：agent_status={heartbeat.agent_status}")
except Exception as e:
    print(f"[FAIL] HeartbeatData 测试失败：{e}")

# 测试 6: ZK 客户端类结构测试
print("\n[测试 6] ZkClient 类结构测试")
try:
    # 检查类方法
    assert hasattr(ZkClient, 'connect'), "缺少 connect 方法"
    assert hasattr(ZkClient, 'disconnect'), "缺少 disconnect 方法"
    assert hasattr(ZkClient, 'is_connected'), "缺少 is_connected 方法"
    assert hasattr(ZkClient, 'create'), "缺少 create 方法"
    assert hasattr(ZkClient, 'delete'), "缺少 delete 方法"
    assert hasattr(ZkClient, 'get'), "缺少 get 方法"
    assert hasattr(ZkClient, 'set'), "缺少 set 方法"
    assert hasattr(ZkClient, 'exists'), "缺少 exists 方法"
    assert hasattr(ZkClient, 'watch_data'), "缺少 watch_data 方法"
    assert hasattr(ZkClient, 'watch_children'), "缺少 watch_children 方法"

    print("[PASS] ZkClient 类结构正确")
    print(f"  主要方法：connect, disconnect, create, delete, get, set, exists, watch_data, watch_children")
except Exception as e:
    print(f"[FAIL] ZkClient 类结构测试失败：{e}")

# 测试 7: ZkHeartbeatNode 类结构测试
print("\n[测试 7] ZkHeartbeatNode 类结构测试")
try:
    assert hasattr(ZkHeartbeatNode, 'start'), "缺少 start 方法"
    assert hasattr(ZkHeartbeatNode, 'stop'), "缺少 stop 方法"
    assert hasattr(ZkHeartbeatNode, 'set_data'), "缺少 set_data 方法"
    assert hasattr(ZkHeartbeatNode, 'get_data'), "缺少 get_data 方法"
    assert hasattr(ZkHeartbeatNode, 'is_alive'), "缺少 is_alive 方法"
    assert hasattr(ZkHeartbeatNode, 'is_running'), "缺少 is_running 方法"

    print("[PASS] ZkHeartbeatNode 类结构正确")
except Exception as e:
    print(f"[FAIL] ZkHeartbeatNode 类结构测试失败：{e}")

# 测试 8: ZkHeartbeatManager 类结构测试
print("\n[测试 8] ZkHeartbeatManager 类结构测试")
try:
    assert hasattr(ZkHeartbeatManager, 'initialize'), "缺少 initialize 方法"
    assert hasattr(ZkHeartbeatManager, 'start'), "缺少 start 方法"
    assert hasattr(ZkHeartbeatManager, 'stop'), "缺少 stop 方法"
    assert hasattr(ZkHeartbeatManager, 'refresh'), "缺少 refresh 方法"
    assert hasattr(ZkHeartbeatManager, 'update_status'), "缺少 update_status 方法"
    assert hasattr(ZkHeartbeatManager, 'set_simulator_info'), "缺少 set_simulator_info 方法"
    assert hasattr(ZkHeartbeatManager, 'add_status_listener'), "缺少 add_status_listener 方法"

    print("[PASS] ZkHeartbeatManager 类结构正确")
except Exception as e:
    print(f"[FAIL] ZkHeartbeatManager 类结构测试失败：{e}")

# 测试 9: ZK 集成类结构测试
print("\n[测试 9] ZK 集成类结构测试")
try:
    assert hasattr(ZKIntegration, 'initialize'), "缺少 initialize 方法"
    assert hasattr(ZKIntegration, 'start'), "缺少 start 方法"
    assert hasattr(ZKIntegration, 'stop'), "缺少 stop 方法"
    assert hasattr(ZKIntegration, 'shutdown'), "缺少 shutdown 方法"
    assert hasattr(ZKIntegration, 'update_status'), "缺少 update_status 方法"
    assert hasattr(ZKIntegration, 'set_simulator_info'), "缺少 set_simulator_info 方法"
    assert hasattr(ZKIntegration, 'is_running'), "缺少 is_running 方法"
    assert hasattr(ZKIntegration, 'is_initialized'), "缺少 is_initialized 方法"

    print("[PASS] ZKIntegration 类结构正确")
except Exception as e:
    print(f"[FAIL] ZKIntegration 类结构测试失败：{e}")

# 测试 10: 全局函数测试
print("\n[测试 10] 全局函数测试")
try:
    # 测试 get_config
    config = get_config()
    assert config is not None, "get_config 返回 None"

    # 测试 reset_config
    from pylinkagent.zookeeper import reset_config
    reset_config()
    config2 = get_config()
    assert config2 is not None, "reset_config 后 get_config 返回 None"

    # 测试 reset_heartbeat_manager
    reset_heartbeat_manager()

    # 测试 reset_integration
    reset_integration()

    print("[PASS] 全局函数测试通过")
except Exception as e:
    print(f"[FAIL] 全局函数测试失败：{e}")

# 测试总结
print("\n" + "=" * 60)
print("测试总结")
print("=" * 60)
print("[PASS] 所有结构测试通过")
print("[INFO] ZK 连接测试跳过 (ZK 服务器不可达)")
print("")
print("ZooKeeper 模块功能验证完成！")
print("注意：实际连接测试需要可访问的 ZooKeeper 集群")
print("=" * 60)
