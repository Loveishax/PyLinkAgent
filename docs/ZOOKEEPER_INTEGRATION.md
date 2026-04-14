# PyLinkAgent ZooKeeper 集成指南

> **版本**: v2.0.0  
> **更新日期**: 2026-04-14  
> **P0 任务完成状态**: ✅ 已完成

---

## 一、概述

PyLinkAgent v2.0.0 完成了与 Java LinkAgent 对齐的 ZooKeeper 集成，实现了双心跳机制 (HTTP + ZK)，确保控制台能够实时感知 Agent 的上下线状态。

### 1.1 核心功能

| 功能 | 描述 | 状态 |
|------|------|------|
| **ZK 连接管理** | 基于 kazoo 的 Curator 等价实现 | ✅ |
| **心跳节点注册** | 在 `/config/log/pradar/status/{app}/{agentId}` 创建临时节点 | ✅ |
| **心跳刷新** | 30 秒定时刷新心跳数据 | ✅ |
| **状态管理** | 支持 AgentStatus 状态切换 | ✅ |
| **重连恢复** | 连接中断后自动重建节点 | ✅ |
| **优雅关闭** | 关闭时自动删除 ZK 节点 | ✅ |
| **日志服务器发现** | Watch `/config/log/pradar/server` (待实现) | ⏳ |
| **客户端路径注册** | `/config/log/pradar/client/{app}/{agentId}` (待实现) | ⏳ |

---

## 二、架构设计

### 2.1 模块结构

```
pylinkagent/zookeeper/
├── __init__.py              # 模块导出
├── config.py                # ZK 配置管理 (匹配 CoreConfig)
├── zk_client.py             # ZK 客户端封装 (匹配 CuratorZkClient)
└── zk_heartbeat.py          # 心跳节点管理 (匹配 CuratorZkHeartbeatNode)

pylinkagent/controller/
├── zk_integration.py        # ZK 集成管理器
└── __init__.py              # 导出 ZK 相关接口

pylinkagent/
└── bootstrap.py             # 主启动器 (整合 HTTP + ZK 心跳)
```

### 2.2 心跳流程

```
Agent 启动
    │
    ├─ 1. 连接 ZooKeeper
    │   └─ 地址：7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181
    │
    ├─ 2. 创建状态路径节点
    │   └─ /config/log/pradar/status/{app}/{agentId} (临时节点)
    │
    ├─ 3. 写入心跳数据 (JSON)
    │   ├─ agentId, host, pid
    │   ├─ agentStatus, errorCode, errorMsg
    │   ├─ agentVersion, simulatorVersion
    │   └─ service, port, jars, ...
    │
    ├─ 4. 启动定时刷新线程 (30 秒)
    │   └─ setData 刷新心跳数据
    │
    └─ 5. 监听连接状态
        ├─ RECONNECTED → 重置节点
        ├─ SUSPENDED/LOST → 标记为不存活
        └─ 节点删除 → 自动重建
```

### 2.3 双心跳机制

| 心跳类型 | 协议 | 频率 | 作用 |
|---------|------|------|------|
| **HTTP 心跳** | HTTP POST | 60 秒 | 上报状态、接收命令、配置拉取 |
| **ZK 心跳** | ZK setData | 30 秒 | 实时存在感知、断线自动清理 |

---

## 三、配置说明

### 3.1 配置文件

创建 `config/zk_config.json`:

```json
{
  "zk_servers": "7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181",
  "app_name": "my-app",
  "agent_id": "",
  "env_code": "test",
  "tenant_id": "1",
  "user_id": "",
  "tenant_app_key": "",
  "agent_version": "1.0.0",
  "simulator_version": "1.0.0",
  "tro_web_url": "http://localhost:9999",
  "connection_timeout_ms": 60000,
  "session_timeout_ms": 60000
}
```

### 3.2 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SIMULATOR_ZK_SERVERS` | ZK 服务器地址 | 配置文件值 |
| `SIMULATOR_APP_NAME` | 应用名称 | `default` |
| `SIMULATOR_AGENT_ID` | Agent ID | 自动生成 ({IP}-{PID}) |
| `SIMULATOR_ENV_CODE` | 环境标识 | `test` |
| `SIMULATOR_TENANT_APP_KEY` | 租户 AppKey | `` |
| `REGISTER_NAME` | 注册中心类型 | `zookeeper` |
| `ZK_ENABLED` | 是否启用 ZK | `true` |

### 3.3 Agent ID 生成规则

```python
# 默认格式：{IP}-{PID}
agent_id = "192.168.1.100-12345"

# 完整格式 (包含租户信息)
full_agent_id = "{agent_id}&{env_code}:{user_id}:{tenant_app_key}"
# 示例：192.168.1.100-12345&test:user1:tenantKey123
```

---

## 四、使用指南

### 4.1 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置环境变量
export MANAGEMENT_URL=http://localhost:9999
export APP_NAME=my-app
export AGENT_ID=agent-001

# 3. 启动 Agent
python scripts/quickstart_agent.py
```

### 4.2 作为库使用

```python
from pylinkagent import bootstrap, shutdown

# 启动 Agent (自动启用 ZK 心跳)
bootstrapper = bootstrap()

# 运行
try:
    bootstrapper.wait()
except KeyboardInterrupt:
    shutdown()
```

### 4.3 手动管理 ZK 集成

```python
from pylinkagent.controller import (
    ZKIntegration,
    get_integration,
    initialize_zk,
    shutdown_zk,
)
from pylinkagent.zookeeper import AgentStatus

# 初始化 ZK
if initialize_zk():
    print("ZK 集成启动成功")

# 获取集成实例
integration = get_integration()

# 更新状态
integration.update_status(AgentStatus.RUNNING)

# 设置 Simulator 信息
integration.set_simulator_info(
    service="http://192.168.1.100:8080",
    port=8080
)

# 关闭 ZK
shutdown_zk()
```

### 4.4 直接使用底层 API

```python
from pylinkagent.zookeeper import (
    ZkConfig,
    ZkClient,
    ZkHeartbeatManager,
    AgentStatus,
    get_config,
    create_client,
)

# 加载配置
config = get_config()

# 创建客户端
client = create_client(config)
client.connect()

# 创建心跳管理器
manager = ZkHeartbeatManager(config, client)
manager.initialize()
manager.start()

# 更新状态
manager.update_status(AgentStatus.RUNNING)

# 停止
manager.stop()
client.disconnect()
```

---

## 五、测试验证

### 5.1 运行测试脚本

```bash
python scripts/test_zk_integration.py
```

### 5.2 验证步骤

1. **连接测试**: 验证能否连接到 ZK 集群
2. **节点创建**: 验证能否创建临时节点
3. **心跳刷新**: 观察 30 秒定时刷新
4. **状态更新**: 验证状态切换功能
5. **优雅关闭**: 验证节点删除

### 5.3 预期输出

```
=== 测试 ZK 配置加载 ===
ZK 服务器：7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181
应用名称：test-pylinkagent-app
Agent ID: test-agent-001
✓ ZK 配置加载成功

=== 测试 ZK 客户端连接 ===
✓ ZK 连接成功：7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181
✓ 临时节点创建成功：/test/pylinkagent/connection_test
✓ 节点数据读取成功：b'test_data'
✓ 节点删除成功：/test/pylinkagent/connection_test

=== 测试心跳管理器 ===
✓ 心跳管理器初始化成功
✓ 心跳管理器启动成功
✓ 状态更新为 RUNNING
等待 35 秒观察心跳刷新...
✓ 心跳节点存活
✓ 心跳管理器已停止

=== 测试 ZK 完整集成 ===
✓ ZK 集成启动成功
✓ ZK 心跳运行中
✓ 状态已更新
✓ ZK 集成已关闭

测试完成!
```

---

## 六、与 Java LinkAgent 对比

### 6.1 功能对齐

| 功能 | Java LinkAgent | PyLinkAgent | 状态 |
|------|----------------|-------------|------|
| ZK 客户端 | Curator Framework | kazoo | ✅ 对等 |
| 心跳节点 | CuratorZkHeartbeatNode | ZkHeartbeatNode | ✅ 对等 |
| 配置管理 | CoreConfig | ZkConfig | ✅ 对等 |
| AgentId 生成 | AddressUtils + PidUtils | socket + os.getpid | ✅ 对等 |
| 心跳数据 | getHeartbeatDatas() | _get_heartbeat_data() | ✅ 对等 |
| 状态监听 | ConnectionStateListener | _on_connection_state_change | ✅ 对等 |
| 节点 Watch | NodeDeleted Watcher | _add_node_watch | ✅ 对等 |
| 定时刷新 | 30 秒 refresh | 30 秒 refresh | ✅ 对等 |

### 6.2 待实现功能 (P2/P3)

| 功能 | 优先级 | 描述 |
|------|--------|------|
| **客户端路径注册** | P1 | `/config/log/pradar/client/{app}/{agentId}` |
| **日志服务器发现** | P2 | Watch `/config/log/pradar/server` |
| **影子 MQ 配置** | P2 | Kafka/ONS 影子配置拉取 |
| **Trace 规则** | P2 | Trace 入口规则拉取 |
| **挡板配置** | P3 | Mock 配置支持 |

---

## 七、故障排查

### 7.1 连接失败

**问题**: 无法连接到 ZooKeeper

**排查步骤**:
```bash
# 1. 检查 ZK 服务是否运行
telnet 7.198.155.26 2181

# 2. 检查防火墙
netsh advfirewall show allprofiles

# 3. 测试 kazoo 连接
python -c "from kazoo.client import KazooClient; c=KazooClient('7.198.155.26:2181'); c.start(); print(c.connected)"
```

### 7.2 节点创建失败

**问题**: 无法创建 ZK 节点

**可能原因**:
- 父路径不存在
- 权限不足
- 节点已存在

**解决方案**:
```python
# 确保父路径存在
client.ensure_path_exists("/config/log/pradar/status")
```

### 7.3 心跳不刷新

**问题**: 心跳节点数据不更新

**排查步骤**:
1. 检查刷新线程是否启动
2. 检查连接状态是否正常
3. 查看日志输出

---

## 八、依赖安装

### 8.1 安装 kazoo

```bash
pip install kazoo>=2.9.0
```

### 8.2 完整依赖

```bash
pip install -r requirements.txt
```

其中新增依赖:
- `kazoo>=2.9.0` - ZooKeeper Python 客户端

---

## 九、API 参考

### 9.1 ZkConfig

```python
@dataclass
class ZkConfig:
    zk_servers: str = "7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181"
    status_base_path: str = "/config/log/pradar/status"
    client_base_path: str = "/config/log/pradar/client"
    server_base_path: str = "/config/log/pradar/server"
    connection_timeout_ms: int = 60000
    session_timeout_ms: int = 60000
    app_name: str = "default"
    agent_id: Optional[str] = None
    env_code: str = "test"
    
    def get_full_agent_id() -> str
    def get_status_path() -> str
    def get_client_path() -> str
```

### 9.2 ZkClient

```python
class ZkClient:
    def connect() -> bool
    def disconnect() -> None
    def is_connected() -> bool
    def create(path, data, ephemeral) -> bool
    def delete(path) -> bool
    def get(path) -> bytes
    def set(path, data) -> bool
    def exists(path) -> bool
    def watch_data(path, callback) -> bool
    def watch_children(path, callback) -> bool
```

### 9.3 ZkHeartbeatManager

```python
class ZkHeartbeatManager:
    def initialize(client) -> bool
    def start() -> bool
    def stop() -> None
    def refresh() -> bool
    def update_status(status, error_msg) -> None
    def set_simulator_info(service, port, md5, jars) -> None
```

---

## 十、总结

### 10.1 完成情况

✅ **P0 任务完成**:
- ZooKeeper 配置模块
- ZooKeeper 客户端封装
- 心跳节点管理
- 心跳管理器
- 集成到主启动流程
- 测试脚本和文档

### 10.2 下一步

- [ ] 客户端路径注册 (`/config/log/pradar/client`)
- [ ] 日志服务器发现 (Watch `/config/log/pradar/server`)
- [ ] P1 配置端点补充 (Redis/ES/Kafka)
- [ ] P2 Trace 规则和挡板配置

### 10.3 资源

- [Java LinkAgent 参考实现](../../simulator-agent/)
- [GAP_ANALYSIS.md](GAP_ANALYSIS.md)
- [README.md](README.md)

---

**文档完成日期**: 2026-04-14  
**版本**: v1.0
