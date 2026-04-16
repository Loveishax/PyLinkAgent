# PyLinkAgent 客户端路径注册功能

> **版本**: v2.0.0  
> **更新日期**: 2026-04-17  
> **主题**: ZooKeeper 客户端路径注册与配置监听

---

## 一、概述

客户端路径注册功能用于在 ZooKeeper 中注册 Agent 客户端信息，并监听控制台下发的配置和命令。

### 1.1 功能特性

- **客户端注册**: 在 ZK 中创建客户端节点，注册 Agent 信息
- **配置监听**: 监听配置目录变化，实现配置热更新
- **命令监听**: 监听命令目录变化，接收控制台命令
- **断线重连**: ZK 连接断开后自动恢复

### 1.2 ZooKeeper 节点结构

```
/config/log/pradar/client/
└── {appName}/
    └── {agentId}/                    # 客户端持久节点
        ├── configs/                  # 配置目录
        │   ├── config-1              # 配置项 1
        │   ├── config-2              # 配置项 2
        │   └── ...
        └── commands/                 # 命令目录
            ├── command-1             # 命令 1
            ├── command-2             # 命令 2
            └── ...
```

---

## 二、核心类说明

### 2.1 ClientNodeData

客户端节点数据结构，存储 Agent 注册信息。

```python
from pylinkagent.zookeeper import ClientNodeData

data = ClientNodeData(
    address="192.168.1.100",
    host="my-host",
    name="my-app",
    pid="12345",
    agent_id="192.168.1.100-12345&test::",
    agent_version="2.0.0",
    simulator_version="2.0.0",
    tenant_app_key="ed45ef6b-bf94-48fa-b0c0-15e0285365d2",
    env_code="test",
    user_id="1",
    capabilities=["config_fetch", "command_poll"],
)
```

### 2.2 ZkClientPathNode

客户端路径节点，管理 ZK 中的持久节点。

```python
from pylinkagent.zookeeper import ZkClientPathNode

node = ZkClientPathNode(client, path, data)
node.start()           # 启动节点
node.set_data(data)    # 更新数据
node.stop()            # 停止节点
```

### 2.3 ZkPathChildrenCache

子节点缓存，监听目录下的子节点变化。

```python
from pylinkagent.zookeeper import ZkPathChildrenCache

cache = ZkPathChildrenCache(client, path)
cache.set_update_listener(lambda: print("配置变化"))
cache.start()                # 启动缓存
children = cache.get_children()  # 获取子节点
added = cache.get_added_children()   # 获取新增子节点
deleted = cache.get_deleted_children() # 获取删除子节点
```

### 2.4 ZkClientPathRegister

客户端路径注册器，整合所有功能。

```python
from pylinkagent.zookeeper import ZkClientPathRegister

register = ZkClientPathRegister(config)
register.initialize()
register.add_config_listener(lambda children: print(f"配置：{children}"))
register.add_command_listener(lambda children: print(f"命令：{children}"))
register.start()
```

---

## 三、使用指南

### 3.1 基础使用

```python
from pylinkagent.zookeeper import (
    get_config,
    create_client,
    ZkClientPathRegister,
    ClientNodeData,
)

# 1. 加载配置
config = get_config()

# 2. 创建 ZK 客户端
client = create_client(config)
if not client.connect():
    raise RuntimeError("ZK 连接失败")

# 3. 创建注册器
register = ZkClientPathRegister(config, client)

# 4. 添加监听器
def on_config_change(children):
    """配置变化回调"""
    for child in children:
        config_path = f"{config.get_client_path()}/configs/{child}"
        config_data = client.get(config_path)
        print(f"新配置：{config_data}")

def on_command_change(children):
    """命令变化回调"""
    for child in children:
        command_path = f"{config.get_client_path()}/commands/{child}"
        command_data = client.get(command_path)
        print(f"新命令：{command_data}")

register.add_config_listener(on_config_change)
register.add_command_listener(on_command_change)

# 5. 启动注册器
if register.start():
    print("客户端路径注册成功")

# 6. 运行... (主线程等待)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

# 7. 停止注册器
register.stop()
client.disconnect()
```

### 3.2 与 bootstrap 集成

修改 `bootstrap.py` 集成客户端路径注册：

```python
from pylinkagent.zookeeper import get_client_path_register

def _init_zookeeper_client_path(self) -> None:
    """初始化 ZooKeeper 客户端路径注册"""
    from pylinkagent.zookeeper import initialize_zk, get_client_path_register

    logger.info("初始化 ZooKeeper 客户端路径注册...")

    register = get_client_path_register()
    if register and register.initialize():
        if register.start():
            logger.info("  ZooKeeper 客户端路径注册已启用")

            # 添加配置监听
            def on_config_change(children):
                logger.info(f"收到 {len(children)} 个配置")
                # 处理配置...

            # 添加命令监听
            def on_command_change(children):
                logger.info(f"收到 {len(children)} 个命令")
                # 处理命令...

            register.add_config_listener(on_config_change)
            register.add_command_listener(on_command_change)
        else:
            logger.warning("  ZooKeeper 客户端路径注册启动失败")
    else:
        logger.info("  ZooKeeper 客户端路径注册未启用")
```

---

## 四、配置说明

### 4.1 路径配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `client_base_path` | `/config/log/pradar/client` | 客户端基础路径 |
| `status_base_path` | `/config/log/pradar/status` | 状态基础路径 |
| `server_base_path` | `/config/log/pradar/server` | 服务器基础路径 |

### 4.2 环境变量

```bash
# ZK 服务器地址
export SIMULATOR_ZK_SERVERS="7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181"

# 应用信息
export SIMULATOR_APP_NAME="my-app"
export SIMULATOR_AGENT_ID="192.168.1.100-12345"
export SIMULATOR_ENV_CODE="test"
export SIMULATOR_USER_ID="1"
export SIMULATOR_TENANT_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"

# 版本信息
export SIMULATOR_AGENT_VERSION="2.0.0"
export SIMULATOR_VERSION="2.0.0"
```

---

## 五、监听器详解

### 5.1 配置监听器

配置监听器在配置目录发生变化时触发：

```python
def on_config_change(children: List[str]) -> None:
    """
    配置变化回调

    Args:
        children: 配置子节点列表
    """
    for child in children:
        # 获取配置数据
        config_path = f"{client_path}/configs/{child}"
        config_data = zk_client.get(config_path)

        # 解析配置
        config = json.loads(config_data.decode('utf-8'))

        # 应用配置...
```

### 5.2 命令监听器

命令监听器在命令目录发生变化时触发：

```python
def on_command_change(children: List[str]) -> None:
    """
    命令变化回调

    Args:
        children: 命令子节点列表
    """
    for child in children:
        # 获取命令数据
        command_path = f"{client_path}/commands/{child}"
        command_data = zk_client.get(command_path)

        # 解析命令
        command = json.loads(command_data.decode('utf-8'))

        # 执行命令...
```

---

## 六、断线重连机制

### 6.1 自动重连

客户端路径注册器内置断线重连机制：

1. **检测断开**: 监听 ZK 连接状态
2. **等待重连**: 等待 ZK 客户端自动重连
3. **恢复节点**: 重连后重新注册节点
4. **刷新缓存**: 重新加载子节点列表

### 6.2 状态流转

```
CONNECTED ──► SUSPENDED/LOST ──► RECONNECTED ──► 恢复节点
```

---

## 七、测试方法

### 7.1 运行测试脚本

```bash
cd PyLinkAgent
python scripts/test_zk_client_path.py
```

### 7.2 手动验证

使用 zkCli 验证：

```bash
# 连接到 ZK
zkCli.sh -server 7.198.155.26:2181

# 查看客户端路径
ls /config/log/pradar/client/{appName}/

# 查看客户端节点数据
get /config/log/pradar/client/{appName}/{agentId}

# 查看配置目录
ls /config/log/pradar/client/{appName}/{agentId}/configs/

# 查看命令目录
ls /config/log/pradar/client/{appName}/{agentId}/commands/
```

---

## 八、与 Java Agent 对比

| 功能 | Java Agent | PyLinkAgent |
|------|------------|-------------|
| 客户端路径 | `/config/log/pradar/client` | 相同 |
| 节点类型 | 持久节点 | 相同 |
| 配置监听 | PathChildrenCache | 相同 |
| 命令监听 | PathChildrenCache | 相同 |
| 断线重连 | ConnectionStateListener | 相同 |
| 数据格式 | JSON | 相同 |

---

## 九、相关文件

| 文件 | 说明 |
|------|------|
| `pylinkagent/zookeeper/zk_client_path.py` | 客户端路径注册核心实现 |
| `pylinkagent/zookeeper/zk_client.py` | ZK 客户端封装 |
| `pylinkagent/zookeeper/config.py` | ZK 配置管理 |
| `scripts/test_zk_client_path.py` | 测试脚本 |

---

## 十、常见问题

### Q1: 客户端路径和心跳路径有什么区别？

- **心跳路径** (`/status`): 临时节点，会话断开后自动删除，用于心跳上报
- **客户端路径** (`/client`): 持久节点，用于配置和命令下发

### Q2: 为什么配置和命令没有及时响应？

检查：
1. ZK 连接是否正常
2. 监听器是否正确注册
3. 子节点缓存是否启动

### Q3: 如何调试配置监听？

启用调试日志：
```python
import logging
logging.getLogger('pylinkagent.zookeeper').setLevel(logging.DEBUG)
```

---

**文档完成日期**: 2026-04-17  
**版本**: v1.0
