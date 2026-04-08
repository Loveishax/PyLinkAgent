# PyLinkAgent 控制台对接快速指南

## 快速开始

### 1. 安装依赖

```bash
pip install httpx  # 推荐使用 httpx，支持 requests 降级
```

### 2. 基本使用

```python
from pylinkagent.controller import (
    ExternalAPI,
    HeartbeatReporter,
    CommandPoller,
    ConfigFetcher,
)

# 初始化 ExternalAPI
api = ExternalAPI(
    tro_web_url="http://localhost:8080",
    app_name="my-app",
    agent_id="agent-001",
)

# 初始化连接
if api.initialize():
    print("控制台连接成功")
else:
    print("控制台连接失败")
    exit(1)

# 启动心跳上报 (30 秒间隔)
heartbeat = HeartbeatReporter(api, interval=30)
heartbeat.start()

# 启动命令轮询 (30 秒间隔)
poller = CommandPoller(api, interval=30, auto_start=True)

# 启动配置拉取 (60 秒间隔)
fetcher = ConfigFetcher(api, interval=60)
fetcher.start()

print("PyLinkAgent 控制器已启动")

# ... 运行应用 ...

# 停止
poller.stop()
fetcher.stop()
heartbeat.stop()
api.shutdown()
```

### 3. 配置方式

#### 方式一：直接配置

```python
api = ExternalAPI(
    tro_web_url="http://tro-console:8080",
    app_name="my-application",
    agent_id="agent-001",
    api_key="your-api-key",  # 可选
    timeout=30,
)
```

#### 方式二：环境变量

```bash
export TRO_WEB_URL=http://tro-console:8080
export APP_NAME=my-application
export AGENT_ID=agent-001
export REGISTER_NAME=kafka  # 可选：kafka 或 zookeeper
```

```python
import os

api = ExternalAPI(
    tro_web_url=os.getenv("TRO_WEB_URL"),
    app_name=os.getenv("APP_NAME"),
    agent_id=os.getenv("AGENT_ID"),
)
```

#### 方式三：配置文件

```yaml
# config.yaml
controller:
  tro_web_url: "http://tro-console:8080"
  app_name: "my-application"
  agent_id: "agent-001"
  api_key: ""
  timeout: 30

heartbeat:
  interval: 30  # 秒

command_polling:
  interval: 30  # 秒

config_fetching:
  interval: 60  # 秒
```

```python
import yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)

api = ExternalAPI(
    tro_web_url=config["controller"]["tro_web_url"],
    app_name=config["controller"]["app_name"],
    agent_id=config["controller"]["agent_id"],
)
```

---

## 核心功能

### 心跳上报

```python
from pylinkagent.controller import HeartbeatReporter

reporter = HeartbeatReporter(api, interval=30)

# 更新状态
reporter.update_status(
    agent_status="running",
    simulator_status="running",
    agent_version="1.0.0",
)

# 设置错误信息
reporter.set_agent_error("连接数据库失败")
reporter.set_simulator_error("模块加载失败")

# 添加命令执行结果
reporter.add_command_result(
    command_id=123,
    is_success=True,
)

# 立即发送心跳
commands = reporter.send_heartbeat_now()
```

### 命令轮询

```python
from pylinkagent.controller import CommandPoller

poller = CommandPoller(api, interval=30)

# 注册命令处理器
def handle_install(command):
    print(f"安装命令：{command.data_path}")
    # 执行安装逻辑
    return True

def handle_uninstall(command):
    print("卸载命令")
    return True

def handle_upgrade(command):
    print(f"升级命令：{command.data_path}")
    return True

# 注册框架命令处理器
poller.register_command_handler(
    command_type=1,  # 框架命令
    handler=handle_install,
)

# 注册模块命令处理器
poller.register_command_handler(
    command_type=2,  # 模块命令
    handler=handle_upgrade,
)

# 设置命令结果回调
def on_result(command_id, success, error_msg):
    print(f"命令 {command_id}: {'成功' if success else '失败'}")

poller.set_on_command_result(on_result)

# 启动
poller.start()

# 立即轮询
commands = poller.poll_now()
```

### 配置拉取

```python
from pylinkagent.controller import ConfigFetcher

fetcher = ConfigFetcher(api, interval=60)

# 注册配置变更回调
def on_change(key, old_value, new_value):
    print(f"配置变更：{key}")
    print(f"  旧：{old_value}")
    print(f"  新：{new_value}")

fetcher.on_config_change(on_change)

# 启动
fetcher.start()

# 获取配置
config = fetcher.get_config()

# 获取影子库配置
shadow_db = fetcher.get_shadow_database_config("mysql-primary")
all_shadow = fetcher.get_all_shadow_database_configs()

# 检查全局开关
if fetcher.is_global_switch_enabled("shadow.database.enable"):
    print("影子库已启用")

# 立即拉取
fetcher.fetch_now()
```

---

## 数据模型

### CommandPacket (命令包)

```python
from pylinkagent.controller import CommandPacket

# 创建命令包
cmd = CommandPacket(
    id=123,
    command_type=1,       # 1: 框架命令，2: 模块命令
    operate_type=1,       # 1: 安装，2: 卸载，3: 升级
    data_path="http://...",
    live_time=-1,         # -1: 无限
)

# 从字典创建
cmd = CommandPacket.from_dict({
    "id": 123,
    "commandType": 2,
    "operateType": 1,
    "dataPath": "http://...",
})

# 无操作命令包
no_op = CommandPacket.no_action_packet()
if cmd.id == -1:
    print("无命令")
```

### HeartRequest (心跳请求)

```python
from pylinkagent.controller import HeartRequest

heart = HeartRequest(
    project_name="my-app",
    agent_id="agent-001",
    ip_address="192.168.1.1",
    progress_id="12345",
    agent_status="running",
    simulator_status="running",
    command_result=[
        {"commandId": 123, "success": True},
    ],
)

# 转换为字典 (用于 API 调用)
data = heart.to_dict()
```

---

## 高级用法

### 自定义命令处理器

```python
from pylinkagent.controller import CommandPoller, CommandPacket

poller = CommandPoller(api)

# 自定义模块安装处理器
def install_module(command):
    data_path = command.data_path
    extras = command.extras
    
    # 下载模块
    if data_path.startswith("http"):
        filepath = api.download_module(data_path, "./modules")
        print(f"模块下载到：{filepath}")
    
    # 解析额外参数
    module_name = extras.get("moduleName")
    module_version = extras.get("version")
    
    # 执行安装逻辑
    # ...
    
    return True

poller.register_command_handler(
    CommandPacket.COMMAND_TYPE_MODULE,
    install_module,
)
```

### 配置变更处理

```python
from pylinkagent.controller import ConfigFetcher

fetcher = ConfigFetcher(api)

# 影子库配置变更处理
def on_shadow_db_change(key, old, new):
    print("影子库配置变更")
    for name, config in new.items():
        if config.get("shadow"):
            print(f"  影子库：{name} -> {config['url']}")
        else:
            print(f"  主库：{name} -> {config['url']}")
    # 重新配置数据源路由
    # update_datasource_routing(new)

fetcher.on_config_change("shadowDatabaseConfigs", on_shadow_db_change)

# 全局开关变更处理
def on_switch_change(key, old, new):
    if key == "shadow.database.enable":
        if new:
            print("启用影子库路由")
            # enable_shadow_routing()
        else:
            print("禁用影子库路由")
            # disable_shadow_routing()

fetcher.on_config_change("globalSwitch", on_switch_change)
```

---

## 错误处理

```python
from pylinkagent.controller import ExternalAPI

api = ExternalAPI(
    tro_web_url="http://invalid:8080",
    app_name="my-app",
    agent_id="agent-001",
)

try:
    if not api.initialize():
        print("连接失败，使用本地模式")
        # 降级处理
except Exception as e:
    print(f"初始化异常：{e}")
    # 错误处理
```

---

## 测试

```bash
# 运行控制器测试
python -m pytest tests/test_controller_integration.py -v

# 运行所有测试
python -m pytest tests/ -v
```

---

## API 参考

### ExternalAPI

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `initialize()` | - | bool | 初始化 API 客户端 |
| `shutdown()` | - | None | 关闭 API 客户端 |
| `is_initialized()` | - | bool | 检查是否已初始化 |
| `get_latest_command()` | - | CommandPacket | 获取最新命令 |
| `send_heartbeat()` | HeartRequest | List[CommandPacket] | 发送心跳 |
| `report_command_result()` | command_id, is_success, error_msg | bool | 上报结果 |
| `download_module()` | download_url, target_path | str | 下载模块 |

### HeartbeatReporter

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `start()` | - | bool | 启动心跳 |
| `stop()` | - | None | 停止心跳 |
| `is_running()` | - | bool | 检查运行状态 |
| `update_status()` | **kwargs | None | 更新状态 |
| `send_heartbeat_now()` | - | List[CommandPacket] | 立即发送 |

### CommandPoller

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `start()` | - | bool | 启动轮询 |
| `stop()` | - | None | 停止轮询 |
| `is_running()` | - | bool | 检查运行状态 |
| `poll_now()` | - | List[CommandPacket] | 立即轮询 |
| `register_command_handler()` | command_type, handler | None | 注册处理器 |

### ConfigFetcher

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `start()` | - | bool | 启动拉取 |
| `stop()` | - | None | 停止拉取 |
| `is_running()` | - | bool | 检查运行状态 |
| `fetch_now()` | - | ConfigData | 立即拉取 |
| `get_config()` | - | ConfigData | 获取当前配置 |
| `on_config_change()` | callback | None | 注册回调 |

---

## 故障排查

### 连接失败

1. 检查 `tro_web_url` 是否正确
2. 检查网络连通性
3. 检查防火墙设置
4. 查看日志输出

### 命令不执行

1. 检查命令处理器是否注册
2. 检查命令类型是否匹配
3. 查看命令 ID 是否为 -1 (无命令)

### 配置不更新

1. 检查配置拉取间隔
2. 检查控制台是否返回配置
3. 查看配置变更回调是否注册

---

**文档版本**: v1.0  
**更新时间**: 2026-04-08
