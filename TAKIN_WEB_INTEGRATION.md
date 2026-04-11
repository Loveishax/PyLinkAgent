# PyLinkAgent - Takin-web 对接文档

## 概述

本文档说明 PyLinkAgent 如何与 Takin-web / takin-ee-web 进行正确对接，包括心跳上报和配置拉取。

## 接口对照表

### 心跳上报

| 项目 | 详情 |
|------|------|
| **接口路径** | `/api/agent/heartbeat` |
| **HTTP 方法** | POST |
| **请求体** | `AgentHeartbeatRequest` |
| **响应** | `List<AgentCommandResBO>` (命令数组) |
| **Java Agent 参考** | `ExternalAPIImpl.sendHeart()` |

**请求数据格式**:
```json
{
  "projectName": "my-app",
  "agentId": "agent-001",
  "ipAddress": "192.168.1.100",
  "progressId": "12345",
  "curUpgradeBatch": "-1",
  "agentStatus": "running",
  "simulatorStatus": "running",
  "uninstallStatus": 0,
  "dormantStatus": 0,
  "agentVersion": "1.0.0",
  "simulatorVersion": "1.0.0",
  "dependencyInfo": "pylinkagent=1.0.0",
  "flag": "shulieEnterprise",
  "commandResult": []
}
```

**响应数据格式**:
```json
[
  {
    "id": 1,
    "extrasString": "..."
  }
]
```

### 影子库配置拉取

| 项目 | 详情 |
|------|------|
| **接口路径** | `/api/link/ds/configs/pull` |
| **HTTP 方法** | GET |
| **查询参数** | `appName=应用名` |
| **响应** | `{ "success": true, "data": [...] }` |
| **Java Agent 参考** | `ApplicationConfigHttpResolver.getPressureTable4AccessSimple()` |

**响应数据格式**:
```json
{
  "success": true,
  "data": [
    {
      "dataSourceName": "master",
      "url": "jdbc:mysql://master:3306/app",
      "username": "root",
      "shadowUrl": "jdbc:mysql://shadow:3306/app_shadow",
      "shadowUsername": "root_shadow"
    }
  ]
}
```

### 命令拉取

| 项目 | 详情 |
|------|------|
| **接口路径** | `/api/agent/application/node/probe/operate` |
| **HTTP 方法** | GET |
| **查询参数** | `appName=应用名&agentId=AgentID` |
| **响应** | `{ "success": true, "data": {...} }` |
| **Java Agent 参考** | `ExternalAPIImpl.getLatestCommandPacket()` |

### 命令结果上报

| 项目 | 详情 |
|------|------|
| **接口路径** | `/api/agent/application/node/probe/operateResult` |
| **HTTP 方法** | POST |
| **请求体** | `{ "appName": "...", "agentId": "...", "operateResult": "1/0" }` |
| **Java Agent 参考** | `ExternalAPIImpl.reportCommandResult()` |

## PyLinkAgent 使用方式

### 1. 初始化 ExternalAPI

```python
from pylinkagent.controller.external_api import ExternalAPI, HeartRequest

# 创建 ExternalAPI 实例
external_api = ExternalAPI(
    tro_web_url="http://<管理侧 IP>:9999",
    app_name="my-app",
    agent_id="agent-001",
)

# 初始化
if not external_api.initialize():
    print("ExternalAPI 初始化失败")
    sys.exit(1)

print("ExternalAPI 初始化成功")
```

### 2. 心跳上报

```python
# 构建心跳请求
heart_request = HeartRequest(
    project_name="my-app",
    agent_id="agent-001",
    ip_address="192.168.1.100",
    progress_id=str(os.getpid()),
    agent_status="running",
    simulator_status="running",
    uninstall_status=0,
    dormant_status=0,
    agent_version="1.0.0",
    simulator_version="1.0.0",
    dependency_info="pylinkagent=1.0.0",
    flag="shulieEnterprise",
)

# 发送心跳
commands = external_api.send_heartbeat(heart_request)

if commands:
    print(f"收到 {len(commands)} 个待执行命令")
    for cmd in commands:
        print(f"  - 命令 ID: {cmd.id}")
```

### 3. 影子库配置拉取

```python
# 直接调用 ExternalAPI
config_data = external_api.fetch_shadow_database_config()

if config_data:
    print(f"拉取到 {len(config_data)} 个影子库配置")
    for cfg in config_data:
        print(f"  数据源：{cfg['dataSourceName']}")
        print(f"    主库：{cfg['url']}")
        print(f"    影子库：{cfg['shadowUrl']}")
else:
    print("未配置影子库")
```

### 4. 使用 ConfigFetcher 定时拉取配置

```python
from pylinkagent.controller.config_fetcher import ConfigFetcher

# 创建配置拉取器
fetcher = ConfigFetcher(
    external_api=external_api,
    interval=60,  # 60 秒拉取一次
    initial_delay=5,  # 初始延迟 5 秒
)

# 注册配置变更回调
def on_config_change(key, old_value, new_value):
    print(f"配置变更：{key}")
    print(f"  旧值：{old_value}")
    print(f"  新值：{new_value}")

fetcher.on_config_change(on_config_change)

# 启动定时拉取
if not fetcher.start():
    print("配置拉取器启动失败")
    sys.exit(1)

# 获取当前配置
config = fetcher.get_config()
for name, cfg in config.shadow_database_configs.items():
    print(f"影子库 {name}: {cfg.url} -> {cfg.shadow_url}")
```

### 5. 完整示例

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.config_fetcher import ConfigFetcher

def main():
    # 1. 初始化 ExternalAPI
    external_api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="test-app",
        agent_id="agent-001",
    )

    if not external_api.initialize():
        print("ExternalAPI 初始化失败")
        sys.exit(1)

    print("ExternalAPI 初始化成功")

    # 2. 创建心跳上报器
    heart_request = HeartRequest(
        project_name="test-app",
        agent_id="agent-001",
        ip_address="127.0.0.1",
        progress_id=str(os.getpid()),
    )

    # 3. 创建配置拉取器
    fetcher = ConfigFetcher(
        external_api=external_api,
        interval=60,
        initial_delay=5,
    )

    def on_config_change(key, old_value, new_value):
        print(f"配置变更：{key}")

    fetcher.on_config_change(on_config_change)

    if not fetcher.start():
        print("配置拉取器启动失败")
        sys.exit(1)

    print("配置拉取器已启动")

    # 4. 发送一次心跳
    commands = external_api.send_heartbeat(heart_request)
    if commands:
        print(f"心跳返回 {len(commands)} 个命令")

    # 5. 拉取配置
    config = fetcher.fetch_now()
    if config and config.shadow_database_configs:
        print(f"拉取到 {len(config.shadow_database_configs)} 个影子库配置")

    # 6. 保持运行
    print("PyLinkAgent 运行中... (Ctrl+C 停止)")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("正在停止...")
        fetcher.stop()
        external_api.shutdown()
        print("已停止")

if __name__ == "__main__":
    main()
```

## 运行验证脚本

```bash
cd PyLinkAgent

# 使用默认配置 (localhost:9999)
python scripts/test_takin_web_communication.py

# 指定管理侧地址
python scripts/test_takin_web_communication.py \
    --management-url http://192.168.1.100:9999 \
    --app-name my-app \
    --agent-id agent-001
```

## 验证通过标准

### 心跳上报验证

- [x] ExternalAPI 初始化成功
- [x] 心跳请求返回 HTTP 200
- [x] 持续心跳 (3 次) 全部成功
- [x] 命令结果上报成功

### 影子库配置拉取验证

- [x] 影子库配置接口返回成功
- [x] 配置数据解析正确
- [x] ConfigFetcher 正常工作
- [x] 配置变更回调机制正常

## 常见问题

### Q1: 心跳返回 404 错误

**A**: 检查管理侧地址是否正确，确保是 Takin-web 服务 (端口通常为 9999)，而不是 agent-management。

### Q2: 影子库配置返回空

**A**: 管理侧可能未配置影子库数据，需要在 Takin-web 前端配置影子库路由规则。

### Q3: 连接被拒绝

**A**: 确保 Takin-web 服务已启动，并且防火墙允许访问。

## 架构说明

```
┌─────────────────┐
│  PyLinkAgent    │
│                 │
│  ExternalAPI    │◄─── HTTP ───► Takin-web (:9999)
│  - sendHeart()  │     /api/agent/heartbeat
│  - fetchShadow()│     /api/link/ds/configs/pull
│  - report()     │     /api/agent/application/node/probe/...
└─────────────────┘

注意：
- 不是 agent-management 的 /open/agent/heartbeat
- 是 Takin-web 的 /api/agent/heartbeat
```

## 版本兼容性

- **Takin-web**: 所有版本
- **takin-ee-web**: 企业版 (通过 `flag="shulieEnterprise"` 标识)
- **agent-management**: 不兼容 (新一代管理侧，使用不同的 API)

---

**文档版本**: 2.0.0  
**更新日期**: 2026-04-11  
**适用版本**: PyLinkAgent 2.0.0+
