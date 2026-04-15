# PyLinkAgent 请求头配置功能总结

> **版本**: v2.0.0  
> **更新日期**: 2026-04-16  
> **主题**: 请求头灵活配置功能实现

---

## 一、需求背景

PyLinkAgent 与控制台 (Takin-web / Takin-ee-web) 交互时，需要携带特定的请求头以完成身份认证和租户识别。用户要求：

1. 支持灵活的请求头配置方式
2. 必需请求头字段：
   - `userAppKey`
   - `tenantAppKey`
   - `userId`
   - `envCode`
3. 在教程中说明如何给请求头赋值

---

## 二、实现内容

### 2.1 修改的文件

#### `pylinkagent/controller/external_api.py`

**ExternalAPI 构造函数**：
```python
def __init__(
    self,
    tro_web_url: str,
    app_name: str,
    agent_id: str,
    api_key: Optional[str] = None,
    timeout: int = 30,
    extra_headers: Optional[Dict[str, str]] = None,  # 新增参数
):
```

**_get_headers() 方法** - 实现三级优先级：
```python
def _get_headers(self) -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "PyLinkAgent/1.0.0",
    }

    # 优先级 1: JSON 环境变量（最低）
    extra_headers_env = os.getenv("HTTP_MUST_HEADERS", "")
    if extra_headers_env:
        headers.update(json.loads(extra_headers_env))

    # 优先级 2: 单个环境变量（中等）
    user_app_key = os.getenv("USER_APP_KEY", "")
    if user_app_key:
        headers["userAppKey"] = user_app_key
    # ... 其他字段

    # 优先级 3: extra_headers 参数（最高）
    if self.extra_headers:
        headers.update(self.extra_headers)

    return headers
```

#### `pylinkagent/bootstrap.py`

**_init_external_api() 方法** - 从环境变量读取请求头：
```python
def _init_external_api(self) -> bool:
    # 构建请求头（从环境变量读取）
    extra_headers = {}

    user_app_key = os.getenv('USER_APP_KEY', '')
    if user_app_key:
        extra_headers['userAppKey'] = user_app_key

    tenant_app_key = os.getenv('TENANT_APP_KEY', '')
    if tenant_app_key:
        extra_headers['tenantAppKey'] = tenant_app_key

    user_id = os.getenv('USER_ID', '')
    if user_id:
        extra_headers['userId'] = user_id

    env_code = os.getenv('ENV_CODE', 'test')
    if env_code:
        extra_headers['envCode'] = env_code

    self._external_api = ExternalAPI(
        tro_web_url=tro_web_url,
        app_name=app_name,
        agent_id=agent_id,
        extra_headers=extra_headers if extra_headers else None,
    )
```

### 2.2 新增的文件

| 文件 | 说明 |
|------|------|
| `docs/HEADERS_CONFIGURATION.md` | 请求头配置指南 |
| `scripts/test_headers.py` | 请求头配置测试脚本 |
| `scripts/run_agent_example.py` | 运行示例脚本 |

---

## 三、配置方式

### 方式一：环境变量（推荐）

```bash
# Linux / macOS
export USER_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
export TENANT_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
export USER_ID="1"
export ENV_CODE="test"

python scripts/run_agent.py
```

```batch
:: Windows
set USER_APP_KEY=ed45ef6b-bf94-48fa-b0c0-15e0285365d2
set TENANT_APP_KEY=ed45ef6b-bf94-48fa-b0c0-15e0285365d2
set USER_ID=1
set ENV_CODE=test

python scripts\run_agent.py
```

### 方式二：代码中配置

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
```

### 方式三：JSON 格式环境变量

```bash
export HTTP_MUST_HEADERS='{"userAppKey":"xxx","tenantAppKey":"xxx","userId":"1","envCode":"test"}'
```

---

## 四、请求头优先级

从高到低：

1. **`extra_headers` 参数** (最高) - 直接覆盖所有
2. **单个环境变量** - 覆盖 JSON 配置
3. **JSON 格式环境变量** - 作为基础配置
4. **默认值** - 仅 `envCode` 有默认值 `test`

---

## 五、验证方法

### 运行测试脚本

```bash
python scripts/test_headers.py
```

### 预期结果

```
[OK] 测试 1: 从环境变量读取请求头
[OK] 测试 2: 从 extra_headers 参数读取
[OK] 测试 3: 从 JSON 环境变量读取
[OK] 测试 4: 请求头优先级测试
[OK] 测试 5: 默认请求头测试

总计：5/5 测试通过
```

---

## 六、使用示例

### 示例 1：测试环境启动

```bash
#!/bin/bash
# scripts/start_test_agent.sh

export MANAGEMENT_URL="http://test-console.example.com"
export APP_NAME="default_demo-test"
export AGENT_ID="pylinkagent-test-001"

# 请求头配置
export USER_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
export TENANT_APP_KEY="ed45ef6b-bf94-48fa-b0c0-15e0285365d2"
export USER_ID="1"
export ENV_CODE="test"

python scripts/run_agent.py
```

### 示例 2：Docker 部署

```yaml
# docker-compose.yml
services:
  pylinkagent:
    environment:
      - MANAGEMENT_URL=http://console:9999
      - APP_NAME=default_demo
      - USER_APP_KEY=ed45ef6b-bf94-48fa-b0c0-15e0285365d2
      - TENANT_APP_KEY=ed45ef6b-bf94-48fa-b0c0-15e0285365d2
      - USER_ID=1
      - ENV_CODE=test
```

---

## 七、相关文档

- [`HEADERS_CONFIGURATION.md`](HEADERS_CONFIGURATION.md) - 完整配置指南
- [`HEARTBEAT_REQUEST_FORMAT_FIX.md`](HEARTBEAT_REQUEST_FORMAT_FIX.md) - 心跳请求格式修正说明

---

## 八、测试覆盖

| 测试项 | 状态 |
|--------|------|
| 从环境变量读取 | ✓ |
| 从 extra_headers 参数读取 | ✓ |
| 从 JSON 环境变量读取 | ✓ |
| 优先级验证 | ✓ |
| 默认值验证 | ✓ |

---

**文档完成日期**: 2026-04-16  
**版本**: v1.0
