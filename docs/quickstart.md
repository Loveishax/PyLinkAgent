# PyLinkAgent QuickStart

## 快速开始

### 方式一：代码导入（推荐）

在应用入口导入 pylinkagent 并调用 `bootstrap()`：

```python
import os
os.environ['MANAGEMENT_URL'] = 'http://localhost:9999'
os.environ['APP_NAME'] = 'my-app'
os.environ['AGENT_ID'] = 'agent-001'

import pylinkagent
pylinkagent.bootstrap()

# 你的应用代码
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def read_root():
    return {"hello": "world"}
```

### 方式二：环境变量 + 命令行启动

```bash
export MANAGEMENT_URL=http://localhost:9999
export APP_NAME=my-app
export AGENT_ID=agent-001

python -c "import pylinkagent; pylinkagent.bootstrap()" &
# 或直接 import pylinkagent 后再启动应用
python your_app.py
```

### 方式三：作为库单独使用

不需要完整 bootstrap，可以单独使用各个组件：

```python
from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.config_fetcher import ConfigFetcher

api = ExternalAPI(
    tro_web_url="http://localhost:9999",
    app_name="my-app",
    agent_id="agent-001",
)
api.initialize()

# 发送心跳
req = HeartRequest(project_name="my-app", agent_id="agent-001",
                   ip_address="192.168.1.100", progress_id=str(os.getpid()))
api.send_heartbeat(req)

# 拉取配置
configs = api.fetch_shadow_database_config()
print(f"获取到 {len(configs)} 个影子库配置")
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MANAGEMENT_URL` | Takin-web 地址 | `http://localhost:9999` |
| `APP_NAME` | 应用名称 | `default-app` |
| `AGENT_ID` | Agent ID | `pylinkagent-<pid>` |
| `USER_APP_KEY` | 用户 AppKey | 空 |
| `TENANT_APP_KEY` | 租户 AppKey | 空 |
| `USER_ID` | 用户 ID | 空 |
| `ENV_CODE` | 环境代码 | `test` |
| `SHADOW_ROUTING` | 启用影子路由 | `true` |
| `CONFIG_FETCH_INTERVAL` | 配置拉取间隔(秒) | `60` |
| `HEARTBEAT_INTERVAL` | 心跳间隔(秒) | `60` |
| `COMMAND_POLL_INTERVAL` | 命令轮询间隔(秒) | `30` |
| `AUTO_REGISTER_APP` | 自动注册应用 | `true` |

## 验证

```bash
# 验证影子路由
python scripts/verify_shadow_routing.py

# 综合验证（需要 ZK + 控制台）
python scripts/comprehensive_verification.py
```

## 故障排查

### 连接被拒绝

```bash
# 检查控制台是否可访问
curl http://localhost:9999
```

### 配置拉取返回空

- 确认应用在控制台已注册
- 确认已配置影子库数据源

### 影子路由未生效

- 检查 `SHADOW_ROUTING` 环境变量是否为 `true`
- 确认压测流量已染色（`PradarSwitcher` + `Pradar.is_cluster_test()`）

---

**版本**: v2.0.0
**更新日期**: 2026-04-23
