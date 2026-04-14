# PyLinkAgent ZooKeeper 交互与数据入库详解

> **版本**: v2.0.0  
> **更新日期**: 2026-04-15  
> **主题**: ZooKeeper 交互流程、数据写入机制、节点存储原理

---

## 一、整体交互架构

### 1.1 系统架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                        PyLinkAgent                                │
│                                                                   │
│  ┌─────────────────┐                                             │
│  │ ZkHeartbeatNode │                                             │
│  │                 │                                             │
│  │ - start()       │  1. 创建临时节点                              │
│  │ - set_data()    │  2. 刷新心跳数据                             │
│  │ - _reset()      │  3. 重连后重建                               │
│  └────────┬────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │    ZkClient     │  封装 kazoo                                  │
│  │                 │                                             │
│  │ - create()      │  → zk.create(path, data, ephemeral=True)    │
│  │ - set()         │  → zk.set(path, data)                       │
│  │ - delete()      │  → zk.delete(path)                          │
│  │ - get()         │  → zk.get(path)                             │
│  └────────┬────────┘                                             │
│           │                                                       │
│           │ TCP 连接 (端口 2181)                                   │
│           │ ZK 协议 (ZooKeeper Atomic Broadcast Protocol)         │
│           ▼                                                       │
└──────────────────────────────────────────────────────────────────┘
            │
            │ 网络
            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    ZooKeeper 集群 (3 节点)                          │
│                                                                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│  │   ZK-1      │     │   ZK-2      │     │   ZK-3      │        │
│  │  (Leader)   │◄───►│  (Follower) │◄───►│  (Follower) │        │
│  │             │ Quorum │             │ Quorum │             │        │
│  │ 7.198.155.26│     │7.198.153.71 │     │7.198.152.234│        │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘        │
│         │                   │                   │                │
│         │ 写请求 (Create/Set)                   │                │
│         ▼                   ▼                   ▼                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              ZAB 协议 (ZooKeeper Atomic Broadcast)       │   │
│  │                                                          │   │
│  │  1. Leader 接收写请求 → 生成事务 ID (ZXID)                │   │
│  │  2. Leader 提议给 Follower                               │   │
│  │  3. Follower 确认 (ACK)                                  │   │
│  │  4. 超过半数确认后 → Leader 提交事务                     │   │
│  │  5. 数据写入内存数据库 + 事务日志                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   内存数据存储                            │   │
│  │                                                          │   │
│  │  /config/log/pradar/status                               │   │
│  │    └── /your-app                                         │   │
│  │         └── /agent-id-123 (临时节点，心跳数据)            │   │
│  │                                                          │   │
│  │  每个节点包含：                                            │   │
│  │  - data: 字节数组 (心跳 JSON)                             │   │
│  │  - stat: 统计信息 (版本、创建时间等)                       │   │
│  │  - ephemeralOwner: 会话 ID (临时节点特有)                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 交互时序图

```
PyLinkAgent 启动
    │
    ├─ 1. 创建 ZkClient (封装 kazoo.KazooClient)
    │      └─ 配置 ZK 服务器列表
    │
    ├─ 2. connect() - 建立 TCP 连接
    │      └─ 与 ZK 集群握手，建立会话 (Session)
    │      └─ 会话 ID: 0x18c5a3b2e1f0000
    │
    ├─ 3. create() - 创建心跳节点
    │      └─ 发送 CreateRequest 到 ZK Leader
    │         └─ Leader 提议 → Follower 确认 → 写入 ZAB 日志
    │            └─ 节点数据持久化到内存 + 快照
    │
    ├─ 4. set() - 刷新心跳数据 (每 30 秒)
    │      └─ 发送 SetDataRequest 更新节点数据
    │
    └─ 5. disconnect() - 断开连接
           └─ 临时节点自动删除 (Leader 触发清理)
```

---

## 二、代码实现详解

### 2.1 ZkClient 连接 ZooKeeper

**文件**: `pylinkagent/zookeeper/zk_client.py`

```python
def connect(self) -> bool:
    """连接到 ZooKeeper"""
    if self._connected:
        return True

    with self._lock:
        if self._connected:
            return True

        try:
            # 创建 KazooClient
            self._client = KazooClient(
                hosts=self.config.zk_servers,
                timeout=self.config.session_timeout_ms / 1000.0,
                handler=SequentialThreadingHandler(),
                read_only=False,
            )

            # 添加状态监听器
            self._client.add_listener(self._connection_listener)

            # 启动连接
            self._client.start()

            # 等待连接
            if not self._client.connected.wait(
                timeout=self.config.connection_timeout_ms / 1000.0
            ):
                logger.error("ZK 连接超时")
                return False

            self._connected = True
            self._state = ConnectionState.CONNECTED
            logger.info(f"ZK 连接成功：{self.config.zk_servers}")
            return True

        except Exception as e:
            logger.error(f"ZK 连接失败：{e}")
            return False
```

**连接过程**:
1. 创建 `KazooClient` 实例
2. 配置服务器列表：`7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181`
3. 调用 `start()` 启动连接线程
4. 等待 `connected` 事件（超时 60 秒）
5. 连接成功后，会话 ID 由 ZK 分配

---

### 2.2 创建心跳节点

**文件**: `pylinkagent/zookeeper/zk_heartbeat.py`

```python
def start(self) -> bool:
    """启动心跳节点"""
    with self._lock:
        if self._is_running:
            return True

        try:
            # 添加状态监听器
            self.client.add_state_listener(self._on_connection_state_change)

            # 检查节点是否存在，存在则删除
            if self.client.exists(self.path):
                self.client.delete(self.path)
                logger.debug(f"已删除旧节点：{self.path}")

            # 创建临时节点
            self.client.create(self.path, self.data, ephemeral=True)
            logger.info(f"心跳节点创建成功：{self.path}")

            # 重置状态
            self._is_running = True
            self._is_alive = True
            self._is_connected = True

            # 添加节点删除监听
            self._add_node_watch()

            return True

        except Exception as e:
            logger.error(f"心跳节点启动失败：{self.path}, error: {e}")
            return False
```

**关键点**:
- `ephemeral=True` - 创建临时节点，会话断开后自动删除
- 节点路径：`/config/log/pradar/status/{app}/{agentId}`
- 节点数据：心跳 JSON（约 500 字节）

---

### 2.3 刷新心跳数据

```python
def set_data(self, data: bytes) -> bool:
    """设置节点数据（刷新心跳）"""
    with self._lock:
        if not self._is_running or not self._is_alive:
            return False

        try:
            self.data = data
            self.client.set(self.path, data)
            logger.debug(f"心跳数据已更新：{self.path}")
            return True
        except Exception as e:
            logger.error(f"设置心跳数据失败：{self.path}, error: {e}")
            return False
```

**刷新机制**:
- 每 30 秒调用一次 `set_data()`
- 更新心跳数据（JSON 格式）
- 数据版本号 +1

---

## 三、ZooKeeper"入库"详细流程

### 3.1 写入流程

```
┌─────────────┐
│ PyLinkAgent │
└──────┬──────┘
       │
       │ 1. CreateRequest(path, data, ephemeral=true)
       ▼
┌─────────────────────────────────────────────────────────┐
│                      ZK Leader                           │
│                   (7.198.155.26:2181)                    │
│                                                          │
│  接收请求 → 生成 ZXID (事务 ID)                           │
│  例如：ZXID = 0x1000001a                                │
└──────────┬──────────────────────────────────────────────┘
           │
           │ 2. Proposal (ZXID=0x1000001a, CREATE /path)
           │
           ├─────────────────┬─────────────────────────┐
           ▼                 ▼                         ▼
     ┌──────────┐      ┌──────────┐            ┌──────────┐
     │ Follower │      │ Follower │            │ Follower │
     │   ZK-1   │      │   ZK-2   │            │   ZK-3   │
     └────┬─────┘      └────┬─────┘            └────┬─────┘
          │                  │                        │
          │ 3. ACK           │                        │
          │◄─────────────────┼────────────────────────┤
          │                  │                        │
          │                  │ 超过半数确认 (2/3)      │
          │                  │                        │
          │ 4. Commit        │                        │
          │─────────────────►│                        │
          │                  │                        │
          │ 5. 写入内存      │ 5. 写入内存            │
          │ 6. 写日志        │ 6. 写日志              │
          │                  │                        │

```

### 3.2 ZAB 协议 (ZooKeeper Atomic Broadcast)

```
ZAB 协议五阶段:

1. PROPOSAL - Leader 提议
   └─ 接收客户端写请求
   └─ 生成唯一事务 ID (ZXID)
   └─ 向所有 Follower 发送 Proposal

2. ACK - Follower 确认
   └─ Follower 接收 Proposal
   └─ 写入本地事务日志
   └─ 向 Leader 发送 ACK

3. COMMIT - Leader 提交
   └─ Leader 收到超过半数 ACK
   └─ 向所有 Follower 发送 Commit
   └─ 正式提交事务

4. APPLY - 应用事务
   └─ 所有服务器应用事务到内存
   └─ 节点数据更新完成

5. NOTIFY - 通知客户端
   └─ Leader 通知客户端写入成功
   └─ Watch 通知发送给监听者
```

### 3.3 内存数据结构

```java
// ZK 服务器内部数据结构 (简化 Java 代码)

// 全局命名空间
public class DataTree {
    private final ConcurrentHashMap<String, DataNode> nodes;
}

// 节点数据结构
public class DataNode {
    // 节点数据
    private byte[] data;           // 心跳 JSON 字节

    // 统计信息
    private int version;           // 数据版本号 (每次 set +1)
    private long ephemeralOwner;   // 会话 ID (仅临时节点)
    private long createTime;       // 创建时间戳
    private long mtime;            // 最后修改时间戳
    private int dataLength;        // 数据长度

    // 子节点
    private Set<String> children;

    // Watch 监听
    private WatchManager watchManager;
}

// 创建节点示例
DataNode newNode = new DataNode();
newNode.data = jsonBytes;                    // 心跳数据
newNode.version = 0;                         // 初始版本
newNode.createTime = System.currentTimeMillis();
newNode.mtime = System.currentTimeMillis();
newNode.ephemeralOwner = sessionId;          // 会话 ID

nodes.put("/config/log/pradar/status/app/agent-id", newNode);
```

### 3.4 数据持久化

```
ZooKeeper 数据持久化机制:

┌─────────────────────────────────────────────────────────┐
│                    磁盘存储                              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  /var/lib/zookeeper/                                    │
│  ├── version-2/                                         │
│  │   ├── log.100000001        ← 事务日志               │
│  │   ├── snapshot.100000001   ← 数据快照               │
│  │   └── log.100000002                                  │
│  │                                                          │
│  └── myid                   ← 服务器 ID                │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                     内存存储                             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  DataTree (完整树形结构)                                │
│  └─ 所有节点数据保存在内存                              │
│  └─ 高性能读写 (微秒级响应)                             │
│                                                          │
└─────────────────────────────────────────────────────────┘

事务日志内容:
Transaction Log Entry:
  ZXID: 0x1000001a
  Type: CREATE
  Path: /config/log/pradar/status/app/agent-id
  Data: { "agentId": "...", "agentStatus": "RUNNING" ... }
  Ephemeral: true
  SessionId: 0x18c5a3b2e1f0000
  Timestamp: 1713100000000
```

---

## 四、心跳数据内容

### 4.1 数据结构

**文件**: `pylinkagent/zookeeper/zk_heartbeat.py`

```python
@dataclass
class HeartbeatData:
    """心跳数据结构"""
    # 基础信息
    address: str = ""
    host: str = ""
    name: str = ""
    pid: str = ""
    agent_id: str = ""

    # 版本信息
    agent_language: str = "PYTHON"
    agent_version: str = "1.0.0"
    simulator_version: str = "1.0.0"

    # 状态信息
    agent_status: str = AgentStatus.RUNNING.value
    error_code: str = ""
    error_msg: str = ""

    # 租户信息
    tenant_app_key: str = ""
    env_code: str = "test"
    user_id: str = ""

    # Simulator 信息
    service: str = ""
    port: str = ""

    # 其他信息
    md5: str = ""
    jars: List[str] = field(default_factory=list)
```

### 4.2 JSON 格式

```json
{
  "address": "192.168.1.100",
  "host": "my-hostname",
  "name": "my-app",
  "pid": "12345",
  "agentId": "192.168.1.100-12345&test::",
  "agentLanguage": "PYTHON",
  "agentVersion": "2.0.0",
  "simulatorVersion": "2.0.0",
  "agentStatus": "RUNNING",
  "errorCode": "",
  "errorMsg": "",
  "jvmArgs": "",
  "jdkVersion": "Python 3.11.0",
  "jvmArgsCheck": "PASS",
  "tenantAppKey": "",
  "envCode": "test",
  "userId": "",
  "service": "",
  "port": "",
  "md5": "",
  "jars": []
}
```

### 4.3 序列化

```python
def to_json(self) -> bytes:
    """转换为 JSON 字节"""
    return json.dumps(self.to_dict(), ensure_ascii=False).encode('utf-8')

# 示例输出 (512 字节)
b'{"address": "192.168.1.100", "host": "my-host", ...}'
```

---

## 五、临时节点的自动删除

### 5.1 删除机制

```
当 PyLinkAgent 断开连接时:

1. TCP 连接断开 / 会话超时 (60 秒无心跳)
   └─► ZK Leader 检测到会话失效

2. ZK 清理临时节点
   └─► 遍历所有 ephemeralOwner == 失效会话 ID 的节点
   └─► 自动删除这些节点

3. 触发 Watch 通知
   └─► 其他监听该路径的客户端收到 NodeDeleted 事件
   └─► PyLinkAgent 收到通知后重建节点

┌─────────────┐     ┌─────────────┐
│  会话正常   │     │  会话断开   │
├─────────────┤     ├─────────────┤
│ ✓ 节点存在  │     │ ✗ 节点删除  │
│ ✓ 心跳刷新  │     │ (自动清理)  │
└─────────────┘     └─────────────┘
```

### 5.2 代码实现

**文件**: `pylinkagent/zookeeper/zk_heartbeat.py`

```python
def _on_connection_state_change(self, state: ConnectionState) -> None:
    """连接状态变化回调"""
    if state == ConnectionState.RECONNECTED:
        if not self._is_connected:
            self._is_connected = True
            try:
                self._reset()  # 重置节点
                logger.info(f"心跳节点从 RECONNECTED 事件恢复：{self.path}")
            except Exception as e:
                logger.error(f"重连后重置失败：{self.path}, error: {e}")
    elif state in [ConnectionState.SUSPENDED, ConnectionState.LOST]:
        self._is_connected = False
        self._is_alive = False
        logger.warning(f"ZK 连接中断，心跳节点标记为不存活：{self.path}")
```

---

## 六、验证节点已入库

### 6.1 使用 zkCli 验证

```bash
# 1. 连接到 ZK 集群
zkCli.sh -server 7.198.155.26:2181

# 2. 查看状态路径
ls /config/log/pradar/status/

# 3. 查看应用下的 Agent
ls /config/log/pradar/status/your-app/

# 4. 查看心跳节点数据
get /config/log/pradar/status/your-app/your-agent-id

# 输出示例:
# {
#   "agentId": "192.168.1.100-12345&test::",
#   "agentStatus": "RUNNING",
#   "address": "192.168.1.100",
#   "host": "my-hostname",
#   ...
# }
# cversion = 0
# dataVersion = 5
# ephemeralOwner = 0x18c5a3b2e1f0000
# mtime = 1713100000000
# dataLength = 512

# 5. 查看节点统计信息
stat /config/log/pradar/status/your-app/your-agent-id

# 输出示例:
# cversion = 0
# dataVersion = 5
# dataLength = 512
# ephemeralOwner = 0x18c5a3b2e1f0000  ← 临时节点，显示会话 ID
# czxid = 0x1000001a                   ← 创建事务 ID
# mzxid = 0x1000001f                   ← 修改事务 ID
# pzxid = 0
# numChildren = 0
# aversion = 0
# owner = 0
# zone = 0
```

### 6.2 使用 Python 验证

```python
from pylinkagent.zookeeper import get_config, create_client

config = get_config()
client = create_client(config)

if client.connect():
    path = config.get_status_path()
    
    # 检查节点是否存在
    exists = client.exists(path)
    print(f"节点存在：{exists}")
    
    # 获取节点数据
    data = client.get(path)
    print(f"节点数据：{data.decode('utf-8')}")
    
    # 获取节点统计
    stat = client.get_stat(path)
    print(f"版本号：{stat.version}")
    print(f"数据长度：{stat.data_len}")
    print(f"临时所有者：{hex(stat.ephemeral_owner)}")
    
    client.disconnect()
```

---

## 七、与传统数据库对比

| 对比项 | MySQL (传统数据库) | ZooKeeper |
|--------|-------------------|-----------|
| **存储介质** | 磁盘 (B+ 树) | 内存 (数据树) + 磁盘 (日志/快照) |
| **数据模型** | 表/行/列 | 树形节点 (ZNode) |
| **写入方式** | SQL INSERT/UPDATE | Create/Set Request |
| **事务协议** | 两阶段提交 (2PC) | ZAB 协议 (类似 Paxos) |
| **一致性** | ACID | 顺序一致性 |
| **临时数据** | 需要定时清理 (DELETE) | 会话绑定，自动删除 |
| **查询方式** | SQL 查询 | 路径遍历 |
| **响应时间** | 毫秒级 | 微秒级 |
| **写入吞吐** | 高 | 低 (适合元数据) |
| **读吞吐** | 高 | 高 |
| **适用场景** | 业务数据存储 | 协调服务、配置管理 |

---

## 八、总结

### 8.1 ZooKeeper"入库"特点

1. **内存存储** - 所有节点数据保存在内存中，高性能
2. **ZAB 协议** - 保证集群数据一致性
3. **事务日志** - 写操作先写日志，保证持久性
4. **临时节点** - 会话绑定，自动清理
5. **Watch 机制** - 数据变更实时通知

### 8.2 PyLinkAgent 使用场景

| 功能 | ZK 路径 | 节点类型 | 更新频率 |
|------|---------|----------|----------|
| **Agent 状态** | `/config/log/pradar/status/{app}/{agentId}` | 临时 | 30 秒 |
| **Pradar 模块** | `/config/log/pradar/client/{app}/{agentId}` | 临时 | 事件驱动 |
| **日志服务器** | `/config/log/pradar/server/{serverId}` | 持久 |  редко |

### 8.3 关键代码位置

| 功能 | 文件 | 方法 |
|------|------|------|
| ZK 连接 | `zk_client.py` | `connect()` |
| 创建节点 | `zk_client.py` | `create()` |
| 刷新心跳 | `zk_client.py` | `set()` |
| 心跳管理 | `zk_heartbeat.py` | `start()`, `set_data()` |
| 状态监听 | `zk_heartbeat.py` | `_on_connection_state_change()` |

---

**文档完成日期**: 2026-04-15  
**版本**: v1.0
