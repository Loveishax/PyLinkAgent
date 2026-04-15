# PyLinkAgent 请求头配置指南

> **版本**: v2.0.0  
> **更新日期**: 2026-04-16  
> **主题**: 控制台请求头配置说明

---

## 一、背景

PyLinkAgent 与控制台 (Takin-web / Takin-ee-web) 交互时，需要携带特定的请求头以完成身份认证和租户识别。

---

## 二、必需请求头

| 请求头 | 说明 | 示例值 |
|--------|------|--------|
| `userAppKey` | 用户应用密钥 | `ed45ef6b-bf94-48fa-b0c0-15e0285365d2` |
| `tenantAppKey` | 租户应用密钥 | `ed45ef6b-bf94-48fa-b0c0-15e0285365d2` |
| `userId` | 用户 ID | `1` |
| `envCode` | 环境代码 | `test` / `prod` |

---

## 三、配置方式

### 方式一：环境变量（推荐）

启动 PyLinkAgent 前设置环境变量：

```bash
# Linux / macOS
export USER_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
export TENANT_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
export USER_ID="1"
export ENV_CODE="test"

# 启动 Agent
python scripts/run_agent.py
```

```batch
:: Windows CMD
set USER_APP_KEY=ed45ef6b-bf94-48fa-b0c0-15e0285365d2
set TENANT_APP_KEY=ed45ef6b-bf94-48fa-b0c0-15e0285365d2
set USER_ID=1
set ENV_CODE=test

:: 启动 Agent
python scripts\run_agent.py
```

```powershell
# Windows PowerShell
$env:USER_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
$env:TENANT_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
$env:USER_ID="1"
$env:ENV_CODE="test"

# 启动 Agent
python scripts/run_agent.py
```

---

### 方式二：直接在代码中配置

如果使用 `PyLinkAgentBootstrapper` 启动：

```python
import os
from pylinkagent import bootstrap

# 设置环境变量
os.environ['USER_APP_KEY'] = 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2'
os.environ['TENANT_APP_KEY'] = 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2'
os.environ['USER_ID'] = '1'
os.environ['ENV_CODE'] = 'test'

# 启动 Agent
bootstrap()
```

或者直接创建 `ExternalAPI` 实例：

```python
from pylinkagent.controller import ExternalAPI

api = ExternalAPI(
    tro_web_url="http://console.example.com",
    app_name="my-app",
    agent_id="agent-001",
    extra_headers={
        "userAppKey": "ed45ef6b-bf94-48fa-b0c0-15e0285365d2",
        "tenantAppKey": "ed45ef6b-bf94-48fa-b0c0-15e0285365d2",
        "userId": "1",
        "envCode": "test",
    }
)

if api.initialize():
    print("ExternalAPI 初始化成功")
```

---

### 方式三：使用 JSON 格式环境变量

```bash
# Linux / macOS
export HTTP_MUST_HEADERS='{"userAppKey":"ed45ef6b-bf94-48fa-b0c0-15e0285365d2","tenantAppKey":"ed45ef6b-bf94-48fa-b0c0-15e0285365d2","userId":"1","envCode":"test"}'

# 启动 Agent
python scripts/run_agent.py
```

---

## 四、完整配置示例

### 示例 1：测试环境启动脚本

```bash
#!/bin/bash
# scripts/start_test_agent.sh

# 控制台地址
export MANAGEMENT_URL="http://test-console.example.com"

# 应用信息
export APP_NAME="default_demo-test"
export AGENT_ID="pylinkagent-test-001"

# 请求头配置（必需）
export USER_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
export TENANT_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
export USER_ID="1"
export ENV_CODE="test"

# 可选配置
export HEARTBEAT_INTERVAL="60"
export CONFIG_FETCH_INTERVAL="60"
export COMMAND_POLL_INTERVAL="30"
export AUTO_REGISTER_APP="true"

# 启动 Agent
python scripts/run_agent.py
```

### 示例 2：生产环境启动脚本

```bash
#!/bin/bash
# scripts/start_prod_agent.sh

# 控制台地址
export MANAGEMENT_URL="http://prod-console.example.com"

# 应用信息
export APP_NAME="default_demo-prod"
export AGENT_ID="pylinkagent-prod-001"

# 请求头配置（必需）
export USER_APP_KEY="bf94-48fa-ed45-ef6b-b0c0-15e0285365d2"
export TENANT_APP_KEY="bf94-48fa-ed45-ef6b-b0c0-15e0285365d2"
export USER_ID="100"
export ENV_CODE="prod"

# 启动 Agent
python scripts/run_agent.py
```

### 示例 3：Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# 设置环境变量
ENV MANAGEMENT_URL=http://console:9999
ENV APP_NAME=default_demo
ENV USER_APP_KEY=ed45ef6b-bf94-48fa-b0c0-15e0285365d2
ENV TENANT_APP_KEY=ed45ef6b-bf94-48fa-b0c0-15e0285365d2
ENV USER_ID=1
ENV ENV_CODE=test

CMD ["python", "scripts/run_agent.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  pylinkagent:
    build: .
    environment:
      - MANAGEMENT_URL=http://console:9999
      - APP_NAME=default_demo
      - USER_APP_KEY=ed45ef6b-bf94-48fa-b0c0-15e0285365d2
      - TENANT_APP_KEY=ed45ef6b-bf94-48fa-b0c0-15e0285365d2
      - USER_ID=1
      - ENV_CODE=test
```

---

## 五、请求头优先级

当多种方式同时配置请求头时，优先级如下（从高到低）：

1. **`extra_headers` 参数** (最高优先级) - 直接覆盖所有其他配置
2. **单个环境变量** (`USER_APP_KEY`, `TENANT_APP_KEY`, `USER_ID`, `ENV_CODE`) - 覆盖 JSON 配置
3. **JSON 格式环境变量** (`HTTP_MUST_HEADERS`) - 作为基础配置
4. **默认值** (最低优先级) - 仅 `envCode` 有默认值 `test`

**示例**：
```bash
# JSON 配置
export HTTP_MUST_HEADERS='{"userAppKey":"json-key","tenantAppKey":"json-key"}'

# 单个环境变量（会覆盖 JSON）
export USER_APP_KEY="env-user-key"

# Python 代码
api = ExternalAPI(
    tro_web_url="http://localhost:9999",
    app_name="my-app",
    agent_id="agent-001",
    extra_headers={"userAppKey": "param-user-key"}  # 最高优先级，覆盖所有
)
```

最终请求头：
- `userAppKey`: `param-user-key` (来自 extra_headers)
- `tenantAppKey`: `json-key` (来自 JSON，因为没有设置单个环境变量)

---

## 六、验证请求头

运行测试脚本验证请求头是否正确配置：

```bash
python scripts/test_headers.py
```

如果没有测试脚本，可以手动验证：

```python
from pylinkagent.controller import ExternalAPI
import os

# 设置环境变量
os.environ['USER_APP_KEY'] = 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2'
os.environ['TENANT_APP_KEY'] = 'ed45ef6b-bf94-48fa-b0c0-15e0285365d2'
os.environ['USER_ID'] = '1'
os.environ['ENV_CODE'] = 'test'

api = ExternalAPI(
    tro_web_url="http://localhost:9999",
    app_name="test-app",
    agent_id="test-agent",
)

headers = api._get_headers()
print("请求头配置:")
for key, value in headers.items():
    print(f"  {key}: {value}")
```

预期输出：

```
请求头配置:
  Content-Type: application/json
  User-Agent: PyLinkAgent/1.0.0
  userAppKey: ed45ef6b-bf94-48fa-b0c0-15e0285365d2
  tenantAppKey: ed45ef6b-bf94-48fa-b0c0-15e0285365d2
  userId: 1
  envCode: test
```

---

## 七、常见问题

### Q1: 请求头缺失会怎样？

如果缺少必需的请求头，控制台可能返回以下错误：

- `401 Unauthorized` - 未授权访问
- `403 Forbidden` - 权限不足
- 返回空数据或默认数据

### Q2: 如何获取 userAppKey 和 tenantAppKey？

联系系统管理员或在控制台的应用管理页面获取。

### Q3: 可以在运行时动态修改请求头吗？

不支持运行时动态修改。如需修改，请重启 Agent。

### Q4: 不同环境如何切换配置？

使用不同的启动脚本或环境变量配置文件：

```bash
# 测试环境
source scripts/env_test.sh
python scripts/run_agent.py

# 生产环境
source scripts/env_prod.sh
python scripts/run_agent.py
```

---

## 八、相关文件

| 文件 | 说明 |
|------|------|
| `pylinkagent/controller/external_api.py` | ExternalAPI 实现，包含请求头处理逻辑 |
| `pylinkagent/bootstrap.py` | 启动器，从环境变量读取请求头配置 |
| `scripts/run_agent.py` | Agent 启动脚本 |

---

## 九、请求头来源说明

```
┌─────────────────────────────────────────────────────────┐
│                    控制 (Takin-web)                       │
│                                                          │
│  请求头验证流程：                                         │
│  1. 接收请求 → 解析请求头                                │
│  2. 验证 userAppKey → 识别用户应用                       │
│  3. 验证 tenantAppKey → 识别租户                         │
│  4. 验证 userId → 识别操作用户                           │
│  5. 验证 envCode → 识别环境 (test/prod)                  │
│  6. 验证通过 → 返回数据                                  │
│  7. 验证失败 → 返回 401/403                              │
└─────────────────────────────────────────────────────────┘
```

---

**文档完成日期**: 2026-04-16  
**版本**: v1.0
