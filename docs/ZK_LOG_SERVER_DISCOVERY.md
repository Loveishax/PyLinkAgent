# PyLinkAgent 日志服务器发现功能

> **版本**: v2.0.0  
> **更新日期**: 2026-04-17  
> **主题**: ZooKeeper 日志服务器发现与监听

---

## 一、概述

日志服务器发现功能用于在 ZooKeeper 中发现和监听可用的日志服务器，实现日志的动态路由。

### 1.1 功能特性

- **服务器发现**: 自动发现 ZK 中注册的日志服务器
- **实时监听**: 监听服务器上下线变化
- **服务器选择**: 支持轮询和按区域选择服务器
- **断线重连**: ZK 连接断开后自动恢复

### 1.2 ZooKeeper 节点结构

```
/config/log/pradar/server/
├── server-1                      # 服务器节点 1
│   └── {host, port, status...}
├── server-2                      # 服务器节点 2
│   └── {host, port, status...}
└── server-3                      # 服务器节点 3
    └── {host, port, status...}
```

---

## 二、核心类说明

### 2.1 LogServerInfo

日志服务器信息数据结构。

```python
from pylinkagent.zookeeper import LogServerInfo

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
data = server.to_dict()

# 转换为 JSON
json_bytes = server.to_json()

# 从字典创建
server2 = LogServerInfo.from_dict(data)
```

### 2.2 ZkLogServerDiscovery

日志服务器发现器，监听 ZK 中的服务器目录。

```python
from pylinkagent.zookeeper import ZkLogServerDiscovery

discovery = ZkLogServerDiscovery(config, client)
discovery.initialize()
discovery.start()

# 获取服务器列表
servers = discovery.get_servers()
server_ids = discovery.get_server_ids()

# 获取在线服务器
online_servers = discovery.get_online_servers()

# 添加监听器
discovery.add_server_listener(lambda ids: print(f"服务器变化：{ids}"))
```

### 2.3 LogServerSelector

日志服务器选择器，从发现的服务器中选择一个。

```python
from pylinkagent.zookeeper import LogServerSelector

selector = LogServerSelector(discovery)

# 选择一个可用服务器
server = selector.select()

# 按区域选择
server = selector.select_by_region("shanghai")
```

---

## 三、使用指南

### 3.1 基础使用

```python
from pylinkagent.zookeeper import (
    get_config,
    create_client,
    ZkLogServerDiscovery,
    LogServerSelector,
)

# 1. 加载配置
config = get_config()

# 2. 创建 ZK 客户端
client = create_client(config)
if not client.connect():
    raise RuntimeError("ZK 连接失败")

# 3. 创建发现器
discovery = ZkLogServerDiscovery(config, client)

# 4. 初始化并启动
if discovery.initialize() and discovery.start():
    print("日志服务器发现启动成功")

    # 5. 添加监听器
    def on_server_change(server_ids):
        print(f"服务器列表变化：{server_ids}")

    discovery.add_server_listener(on_server_change)

    # 6. 获取服务器列表
    servers = discovery.get_servers()
    for server in servers:
        print(f"服务器：{server.name} - {server.address}")

    # 7. 创建选择器
    selector = LogServerSelector(discovery)
    selected = selector.select()
    if selected:
        print(f"选择的服务器：{selected.address}")

# 8. 运行... (主线程等待)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

# 9. 停止
discovery.stop()
client.disconnect()
```

### 3.2 与 bootstrap 集成

```python
from pylinkagent.zookeeper import get_log_server_discovery

def _init_log_server_discovery(self) -> None:
    """初始化日志服务器发现"""
    logger.info("初始化日志服务器发现...")

    discovery = get_log_server_discovery()
    if discovery and discovery.initialize():
        if discovery.start():
            logger.info("  日志服务器发现已启用")

            # 添加监听器
            def on_server_change(server_ids):
                logger.info(f"收到 {len(server_ids)} 个服务器")
                # 更新本地缓存...

            discovery.add_server_listener(on_server_change)

            # 获取初始服务器列表
            servers = discovery.get_servers()
            logger.info(f"发现 {len(servers)} 个日志服务器")
        else:
            logger.warning("  日志服务器发现启动失败")
    else:
        logger.info("  日志服务器发现未启用")
```

---

## 四、配置说明

### 4.1 路径配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `server_base_path` | `/config/log/pradar/server` | 日志服务器基础路径 |

### 4.2 环境变量

```bash
# ZK 服务器地址
export SIMULATOR_ZK_SERVERS="7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181"

# 日志服务器路径 (可选，自定义)
export SIMULATOR_LOG_SERVER_PATH="/config/log/pradar/server"
```

---

## 五、服务器选择策略

### 5.1 轮询选择

```python
class LogServerSelector:
    def select(self) -> Optional[LogServerInfo]:
        """选择一个可用的服务器"""
        online_servers = self.discovery.get_online_servers()
        if not online_servers:
            return None
        return online_servers[0]  # TODO: 轮询
```

### 5.2 按区域选择

```python
def select_by_region(self, region: str) -> Optional[LogServerInfo]:
    """按区域选择服务器"""
    online_servers = self.discovery.get_online_servers()
    for server in online_servers:
        if server.region == region:
            return server
    return online_servers[0] if online_servers else None
```

### 5.3 自定义选择策略

继承 `LogServerSelector` 实现自定义策略：

```python
class WeightedLogServerSelector(LogServerSelector):
    def __init__(self, discovery, weights: Dict[str, int]):
        super().__init__(discovery)
        self.weights = weights

    def select(self) -> Optional[LogServerInfo]:
        online_servers = self.discovery.get_online_servers()
        if not online_servers:
            return None

        # 按权重选择
        max_weight = 0
        selected = None
        for server in online_servers:
            weight = self.weights.get(server.name, 0)
            if weight > max_weight:
                max_weight = weight
                selected = server
        return selected
```

---

## 六、监听器详解

### 6.1 服务器监听器

```python
def on_server_change(server_ids: List[str]) -> None:
    """
    服务器变化回调

    Args:
        server_ids: 服务器 ID 列表
    """
    for server_id in server_ids:
        server = discovery.get_server(server_id)
        if server and server.status == "online":
            print(f"在线服务器：{server.name} - {server.address}")
```

### 6.2 注册和注销监听器

```python
# 注册监听器
listener_id = discovery.add_server_listener(on_server_change)

# 注销监听器
discovery.remove_server_listener(on_server_change)
```

---

## 七、断线重连机制

### 7.1 自动重连

日志服务器发现器内置断线重连机制：

1. **检测断开**: 监听 ZK 连接状态
2. **等待重连**: 等待 ZK 客户端自动重连
3. **刷新缓存**: 重连后重新加载服务器列表
4. **通知监听器**: 触发监听器通知

### 7.2 状态流转

```
CONNECTED ──► SUSPENDED/LOST ──► RECONNECTED ──► 刷新服务器列表
```

---

## 八、测试方法

### 8.1 运行测试脚本

```bash
cd PyLinkAgent
python scripts/test_zk_log_server.py
```

### 8.2 手动验证

使用 zkCli 验证：

```bash
# 连接到 ZK
zkCli.sh -server 7.198.155.26:2181

# 查看服务器路径
ls /config/log/pradar/server/

# 查看服务器数据
get /config/log/pradar/server/server-1

# 输出示例:
# {
#   "host": "192.168.1.100",
#   "port": 8080,
#   "address": "192.168.1.100:8080",
#   "serverType": "http",
#   "status": "online",
#   "name": "server-1",
#   "region": "shanghai"
# }
```

---

## 九、与 Java Agent 对比

| 功能 | Java Agent | PyLinkAgent |
|------|------------|-------------|
| 服务器路径 | `/config/log/pradar/server` | 相同 |
| 节点类型 | 持久节点 | 相同 |
| 服务器监听 | PathChildrenCache | 相同 |
| 断线重连 | ConnectionStateListener | 相同 |
| 数据格式 | JSON | 相同 |

---

## 十、完整示例

### 10.1 日志上报集成

```python
from pylinkagent.zookeeper import (
    get_config,
    create_client,
    ZkLogServerDiscovery,
    LogServerSelector,
)
import httpx

class LogPusher:
    def __init__(self):
        self.config = get_config()
        self.client = create_client(self.config)
        self.discovery = ZkLogServerDiscovery(self.config, self.client)
        self.selector = LogServerSelector(self.discovery)
        self.current_server = None

    def start(self):
        if self.discovery.initialize() and self.discovery.start():
            self.discovery.add_server_listener(self.on_server_change)
            self.update_current_server()

    def on_server_change(self, server_ids):
        """服务器变化回调"""
        print(f"服务器列表变化：{server_ids}")
        self.update_current_server()

    def update_current_server(self):
        """更新当前服务器"""
        self.current_server = self.selector.select()
        if self.current_server:
            print(f"切换到服务器：{self.current_server.address}")

    def push_log(self, log_data: dict) -> bool:
        """推送日志"""
        if not self.current_server:
            self.update_current_server()

        if not self.current_server:
            print("无可用日志服务器")
            return False

        url = f"http://{self.current_server.address}/api/logs"
        try:
            response = httpx.post(url, json=log_data, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"推送日志失败：{e}")
            # 切换服务器
            self.update_current_server()
            return False

# 使用
pusher = LogPusher()
pusher.start()
pusher.push_log({"message": "test log"})
```

---

## 十一、相关文件

| 文件 | 说明 |
|------|------|
| `pylinkagent/zookeeper/zk_log_server.py` | 日志服务器发现核心实现 |
| `pylinkagent/zookeeper/zk_client.py` | ZK 客户端封装 |
| `pylinkagent/zookeeper/config.py` | ZK 配置管理 |
| `scripts/test_zk_log_server.py` | 测试脚本 |

---

## 十二、常见问题

### Q1: 日志服务器发现心跳发现有什么区别？

- **心跳发现** (`/status`): 临时节点，上报 Agent 状态
- **日志服务器发现** (`/server`): 持久节点，发现日志服务器

### Q2: 为什么服务器列表为空？

检查：
1. ZK 连接是否正常
2. 服务器路径是否正确
3. 是否有服务器注册到 ZK

### Q3: 如何调试服务器监听？

启用调试日志：
```python
import logging
logging.getLogger('pylinkagent.zookeeper').setLevel(logging.DEBUG)
```

---

**文档完成日期**: 2026-04-17  
**版本**: v1.0
