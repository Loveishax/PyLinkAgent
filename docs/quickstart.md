# PyLinkAgent QuickStart

## 快速开始（5 分钟上手）

### 方式一：环境变量注入（推荐，零代码侵入）

```bash
# 1. 安装 PyLinkAgent
pip install pylinkagent

# 2. 设置环境变量
export PYLINKAGENT_ENABLED=true
export PYLINKAGENT_PLATFORM_URL=http://localhost:8080
export PYLINKAGENT_AGENT_ID=my-app-001

# 3. 启动你的应用（无需修改任何代码）
python app.py
```

### 方式二：包装器启动

```bash
# 使用 pylinkagent-run 包装器
pylinkagent-run python app.py

# 或指定配置文件
pylinkagent-run --config /etc/pylinkagent/config.yaml python app.py
```

### 方式三：代码中导入（最早导入）

```python
# 在 app.py 的第一行导入
import pylinkagent
pylinkagent.bootstrap()

# 然后是你的应用代码
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
```

## 配置文件示例

### 最小配置（YAML）

```yaml
# pylinkagent.yaml
enabled: true
app_name: my-fastapi-app
log_level: INFO
```

### 完整配置

```yaml
# /etc/pylinkagent/config.yaml

agent_id: "my-app-001"
app_name: "my-fastapi-app"
enabled: true
log_level: "INFO"

platform:
  url: "http://localhost:8080"
  api_key: "your-api-key-here"
  timeout: 30

reporter:
  enabled: true
  batch_size: 100
  flush_interval: 5.0

sampler:
  trace_sample_rate: 0.1  # 10% 采样率

enabled_modules:
  - requests
  - httpx
  - fastapi
  - sqlalchemy
  - redis

module_configs:
  requests:
    capture_headers: true
    capture_body: false
    ignored_hosts:
      - localhost
      - 127.0.0.1

  fastapi:
    capture_headers: true
    capture_body: false
    ignored_paths:
      - /health
      - /ready
      - /metrics
```

## 验证探针是否工作

### 检查日志输出

```bash
# 启动后应该看到类似日志
[INFO] pylinkagent - PyLinkAgent v1.0.0 正在启动...
[INFO] pylinkagent - Agent 初始化完成，agent_id=my-app-001
[INFO] pylinkagent - Agent 启动成功
[INFO] pylinkagent - PyLinkAgent 启动成功
[INFO] pylinkagent - 正在加载模块：requests
[INFO] pylinkagent - requests 模块插桩成功
```

### 使用命令行工具检查状态

```bash
# 查看探针状态
pylinkagent-cli status
```

## 完整示例：FastAPI 应用

### 示例应用代码

```python
# app.py
from fastapi import FastAPI
import requests

app = FastAPI()

@app.get("/")
def read_root():
    resp = requests.get("https://httpbin.org/get")
    return {"hello": "world", "status": resp.status_code}

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id, "name": f"User {user_id}"}
```

### 启动命令

```bash
# 方式 1：环境变量
export PYLINKAGENT_ENABLED=true
export PYLINKAGENT_PLATFORM_URL=http://localhost:8080
uvicorn app:app --host 0.0.0.0 --port 8000

# 方式 2：包装器
pylinkagent-run uvicorn app:app --host 0.0.0.0 --port 8000
```

## 命令行工具使用

```bash
# 查看帮助
pylinkagent-cli --help

# 查看探针状态
pylinkagent-cli status

# 模块管理
pylinkagent-cli modules list
pylinkagent-cli modules enable requests
pylinkagent-cli modules reload fastapi

# 配置管理
pylinkagent-cli config show
pylinkagent-cli config set sampler.trace_sample_rate 0.5

# 交互式模式
pylinkagent-cli shell
```

## 故障排查

### 探针未启动

```bash
# 检查环境变量
echo $PYLINKAGENT_ENABLED
echo $PYLINKAGENT_PLATFORM_URL

# 检查是否安装
pip show pylinkagent

# 检查导入是否正常
python -c "import pylinkagent; print(pylinkagent.__version__)"
```

### 模块未加载

```bash
# 查看日志
export PYLINKAGENT_LOG_LEVEL=DEBUG
python app.py

# 检查依赖
pip show requests fastapi sqlalchemy
```
