# PyLinkAgent QuickStart

这份文档按“先挂载，再联控制台，再联 ZK，最后做影子库隔离”的顺序写，适合内网环境直接照着执行。

## 1. 安装

```bash
cd PyLinkAgent
pip install -r requirements.txt
pip install -e .
```

如果内网不能联网，建议先在外网环境准备依赖包：

```bash
cd PyLinkAgent
mkdir -p vendor
pip download -r requirements.txt -d vendor
```

把 `PyLinkAgent/` 和 `vendor/` 一起带到内网后安装：

```bash
cd PyLinkAgent
pip install --no-index --find-links=vendor -r requirements.txt
pip install -e .
```

## 2. 最小环境变量

```bash
export PYLINKAGENT_ENABLED=true
export MANAGEMENT_URL=http://<takin-web-host>:<port>
export APP_NAME=<python-app-name>
export AGENT_ID=<plain-agent-id>
```

如果第一轮只想验证挂载，不接控制台和 ZK：

```bash
export ZK_ENABLED=false
export AUTO_REGISTER_APP=false
export SHADOW_ROUTING=false
```

Windows PowerShell 写法：

```powershell
$env:PYLINKAGENT_ENABLED="true"
$env:MANAGEMENT_URL="http://127.0.0.1:9999"
$env:APP_NAME="my-python-app"
$env:AGENT_ID="my-python-agent"
```

## 3. 挂载方式

### 方式一：`sitecustomize`

这是第一优先方案，最接近 Java 静态挂载。

```bash
python app.py
```

前提：

- 已执行 `pip install -e .`
- `PYLINKAGENT_ENABLED=true`

### 方式二：`pylinkagent-run`

```bash
pylinkagent-run python app.py
```

### 方式三：显式导入

排查环境问题时最直接。

```python
import os

os.environ["PYLINKAGENT_ENABLED"] = "true"
os.environ["MANAGEMENT_URL"] = "http://127.0.0.1:9999"
os.environ["APP_NAME"] = "my-python-app"

import pylinkagent
```

## 4. 最小烟测

```bash
python -c "import pylinkagent; print(pylinkagent.is_running()); pylinkagent.shutdown(); print(pylinkagent.is_running())"
```

预期：

- 第一行输出 `True`
- 第二行输出 `False`

## 5. 内网验证顺序

### 第一步：只验挂载

先确认探针能自动启动，不要同时排查控制台、ZK、影子库。

```bash
export PYLINKAGENT_ENABLED=true
export ZK_ENABLED=false
export AUTO_REGISTER_APP=false
export SHADOW_ROUTING=false
python -c "import pylinkagent; print(pylinkagent.is_running()); pylinkagent.shutdown(); print(pylinkagent.is_running())"
```

### 第二步：接控制台

```bash
export PYLINKAGENT_ENABLED=true
export MANAGEMENT_URL=http://<takin-web-host>:<port>
export APP_NAME=<python-app-name>
export AGENT_ID=<plain-agent-id>
export AUTO_REGISTER_APP=true
export ZK_ENABLED=false
export SHADOW_ROUTING=false
python -c "import pylinkagent; import time; time.sleep(90)"
```

观察：

- 控制台是否出现应用
- 控制台是否出现探针安装信息
- 心跳时间是否持续刷新

### 第三步：接 ZooKeeper

```bash
export ZK_ENABLED=true
export REGISTER_NAME=zookeeper
export SIMULATOR_ZK_SERVERS=<zk1:2181,zk2:2181,zk3:2181>
export SIMULATOR_APP_NAME=<python-app-name>
export SIMULATOR_AGENT_ID=<plain-agent-id>
export SIMULATOR_ENV_CODE=<env-code>
export SIMULATOR_USER_ID=<user-id>
export SIMULATOR_TENANT_APP_KEY=<tenant-app-key>
python -c "import pylinkagent; import time; time.sleep(90)"
```

重点检查：

- `/config/log/pradar/client/<appName>/<fullAgentId>` 是否出现
- 节点是否为临时节点
- 节点数据里是否有 `agentLanguage=PYTHON`

### 第四步：开启影子路由

```bash
export SHADOW_ROUTING=true
export HTTP_SERVER_TRACING=true
```

然后配合控制台下发：

- 压测总开关
- 影子库配置

最后再做压测流量隔离验证。

## 6. 推荐直接使用的 Demo

如果你要快速验证“压测 header -> MySQL 影子库”的主链路，直接用：

- [examples/fastapi_mysql_shadow_demo/README.md](../examples/fastapi_mysql_shadow_demo/README.md)

这个 demo 已经在本地真实 MySQL 跑通过。
