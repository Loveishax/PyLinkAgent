# PyLinkAgent 综合验证脚本使用指南

> **版本**: v2.0.0  
> **更新日期**: 2026-04-17  
> **主题**: 综合验证脚本使用说明

---

## 一、验证脚本说明

综合验证脚本用于一键验证 PyLinkAgent 的核心功能：

1. **ZooKeeper 心跳** - 验证 Agent 心跳上报功能
2. **客户端路径注册** - 验证 ZK 客户端注册和配置监听
3. **影子配置拉取** - 验证从控制台拉取影子库和远程调用配置

---

## 二、脚本位置

```
PyLinkAgent/scripts/comprehensive_verification.py
```

---

## 三、运行方式

### 3.1 基本运行

```bash
cd PyLinkAgent
python scripts/comprehensive_verification.py
```

### 3.2 设置环境变量后运行

```bash
# Linux / macOS
export SIMULATOR_ZK_SERVERS="7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181"
export SIMULATOR_APP_NAME="my-app"
export SIMULATOR_AGENT_ID="192.168.1.100-12345"
export SIMULATOR_ENV_CODE="test"
export SIMULATOR_USER_ID="1"
export SIMULATOR_TENANT_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
export MANAGEMENT_URL="http://console.example.com"

python scripts/comprehensive_verification.py
```

```powershell
# Windows PowerShell
$env:SIMULATOR_ZK_SERVERS="7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181"
$env:SIMULATOR_APP_NAME="my-app"
$env:SIMULATOR_AGENT_ID="192.168.1.100-12345"
$env:SIMULATOR_ENV_CODE="test"
$env:MANAGEMENT_URL="http://console.example.com"

python scripts/comprehensive_verification.py
```

---

## 四、验证项目

### 4.1 前置条件检查

```
[步骤 0: 检查前置条件]
--------------------------------------------------
[检查] Python 版本：3.11.9
  [OK] Python >= 3.8: 3.11.9
  [OK] kazoo 已安装
  [OK] httpx 已安装

[检查] 环境变量:
  ✓ SIMULATOR_ZK_SERVERS = 7.198.155.26:2181,...
  ✓ SIMULATOR_APP_NAME = my-app
  ○ SIMULATOR_AGENT_ID = 未设置
  ✓ SIMULATOR_ENV_CODE = test
  ✓ SIMULATOR_USER_ID = 1
  ✓ SIMULATOR_TENANT_APP_KEY = ed45ef6b-...
  ✓ MANAGEMENT_URL = http://console.example.com

前置条件检查总结:
  通过：6/7 测试通过
```

### 4.2 ZooKeeper 心跳验证

```
[验证 1: ZooKeeper 心跳]
======================================================

[加载 ZK 配置]
--------------------------------------------------
  ZK 服务器：7.198.155.26:2181,...
  应用名称：my-app
  完整 Agent ID: 192.168.1.100-12345&test:1:ed45ef6b-...
  状态路径：/config/log/pradar/status/my-app/...
  [OK] 配置加载成功

[连接 ZooKeeper]
--------------------------------------------------
  连接状态：connected
  [OK] ZK 连接成功

[创建心跳节点]
--------------------------------------------------
  [OK] 心跳管理器初始化成功

[启动心跳]
--------------------------------------------------
  [OK] 心跳启动成功
  等待 35 秒观察心跳刷新...
  [OK] 心跳节点存活
  心跳数据：agentStatus=RUNNING
  心跳数据：agentId=192.168.1.100-12345&test:1:ed45ef6b-...
  [OK] ZK 已断开连接

ZooKeeper 心跳验证:
  [OK] config_load
  [OK] zk_connect
  [OK] node_create
  [OK] heartbeat_refresh
  小计：4/4
```

### 4.3 客户端路径注册验证

```
[验证 2: 客户端路径注册]
======================================================

[加载 ZK 配置]
--------------------------------------------------
  客户端路径：/config/log/pradar/client/my-app/...
  [OK] 配置加载成功

[连接 ZooKeeper]
--------------------------------------------------
  [OK] ZK 连接成功

[创建客户端路径注册器]
--------------------------------------------------
  [OK] 客户端路径注册器初始化成功

[启动客户端路径注册]
--------------------------------------------------
  [OK] 客户端路径注册器启动成功
  配置子节点数：0
  命令子节点数：0
  [OK] 监听器添加成功
  等待 5 秒观察监听...
  [OK] 客户端路径注册器已停止

客户端路径注册验证:
  [OK] config_load
  [OK] zk_connect
  [OK] client_node_create
  [OK] config_cache_start
  [OK] command_cache_start
  小计：5/5
```

### 4.4 影子配置拉取验证

```
[验证 3: 影子配置拉取]
======================================================

[初始化 ExternalAPI]
--------------------------------------------------
  控制台地址：http://console.example.com
  应用名称：my-app
  Agent ID: test-agent-12345
  [OK] ExternalAPI 初始化成功

[拉取影子库配置]
--------------------------------------------------
  [OK] 影子库配置拉取成功：2 个数据源
  数据源：master
    主库：jdbc:mysql://master:3306/app
    影子库：jdbc:mysql://shadow:3306/app_shadow
  [OK] 配置格式验证

[拉取远程调用配置]
--------------------------------------------------
  [OK] 远程调用配置拉取成功
  黑名单：5 条
  白名单：3 条
  Mock 配置：2 条

影子配置拉取验证:
  [OK] api_init
  [OK] shadow_db_fetch
  [OK] shadow_db_valid
  [OK] remote_call_fetch
  小计：4/4
```

---

## 五、验证总结

```
[验证总结]
======================================================

ZooKeeper 心跳验证:
  [OK] config_load
  [OK] zk_connect
  [OK] node_create
  [OK] heartbeat_refresh
  小计：4/4

客户端路径注册验证:
  [OK] config_load
  [OK] zk_connect
  [OK] client_node_create
  [OK] config_cache_start
  [OK] command_cache_start
  小计：5/5

影子配置拉取验证:
  [OK] api_init
  [OK] shadow_db_fetch
  [OK] shadow_db_valid
  [OK] remote_call_fetch
  小计：4/4

======================================================================
总计：13/13 测试通过
======================================================================

[SUCCESS] 所有验证通过!
```

---

## 六、快速验证命令

如果只需要验证模块导入和基本配置：

```bash
python -c "
import sys
sys.path.insert(0, 'PyLinkAgent')

from pylinkagent.zookeeper import (
    get_config,
    ZkHeartbeatManager,
    ZkClientPathRegister,
    ZkLogServerDiscovery,
)
from pylinkagent.controller import ExternalAPI, HeartRequest

config = get_config()
print(f'ZK 服务器：{config.zk_servers}')
print(f'应用名称：{config.app_name}')
print(f'客户端路径：{config.get_client_path()}')
print(f'日志服务器路径：{config.server_base_path}')

req = HeartRequest()
data = req.to_dict()
print(f'HeartRequest 格式正确：agentStatus={data[\"agentStatus\"]}')

print('所有模块验证通过')
"
```

---

## 七、故障排查

### 问题 1: kazoo 未安装

```
[FAIL] kazoo 已安装：请运行：pip install kazoo
```

**解决**:
```bash
pip install kazoo>=2.9.0
```

### 问题 2: ZK 连接失败

```
[FAIL] ZK 连接成功
```

**解决**:
1. 检查 ZK 服务器是否运行
2. 检查网络连接
3. 检查 `SIMULATOR_ZK_SERVERS` 环境变量

### 问题 3: 影子配置返回空

```
[FAIL] 影子库配置拉取成功：返回空或失败
```

**解决**:
1. 检查应用在控制台是否配置了影子库
2. 检查 `MANAGEMENT_URL` 是否正确
3. 检查请求头配置（userAppKey, tenantAppKey 等）

---

## 八、相关文件

| 文件 | 说明 |
|------|------|
| `scripts/comprehensive_verification.py` | 综合验证脚本 |
| `scripts/test_zk_client_path.py` | 客户端路径测试 |
| `scripts/test_zk_log_server.py` | 日志服务器测试 |
| `docs/ZK_CLIENT_PATH_REGISTER.md` | 客户端路径文档 |
| `docs/ZK_LOG_SERVER_DISCOVERY.md` | 日志服务器文档 |

---

**文档完成日期**: 2026-04-17  
**版本**: v1.0
