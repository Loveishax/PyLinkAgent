# PyLinkAgent QuickStart

本文档只描述当前代码已经具备的接入方式，不再覆盖旧版 `instrument_simulator` 方案。

## 1. 安装

```bash
cd PyLinkAgent
pip install -r requirements.txt
pip install -e .
```

如果内网环境不能直接访问外网依赖源，建议先在可联网环境准备 wheel 包，再带入内网安装。

可联网环境打包示例：

```bash
cd PyLinkAgent
mkdir -p vendor
pip download -r requirements.txt -d vendor
```

把 `PyLinkAgent/` 目录和 `vendor/` 一并带到内网后安装：

```bash
cd PyLinkAgent
pip install --no-index --find-links=vendor -r requirements.txt
pip install -e .
```

## 2. 最小环境变量

```bash
export PYLINKAGENT_ENABLED=true
export MANAGEMENT_URL=http://localhost:9999
export APP_NAME=my-python-app
export AGENT_ID=my-python-agent
```

如果暂时不接 ZooKeeper 或不想自动注册应用，可以先显式关闭：

```bash
export ZK_ENABLED=false
export AUTO_REGISTER_APP=false
export SHADOW_ROUTING=false
```

## 3. 启动方式

### 方式一：解释器自动加载

```bash
python app.py
```

前提：

- 已 `pip install -e .`
- `PYLINKAGENT_ENABLED=true`

建议先用一个最小脚本确认自动加载生效：

```python
# app.py
import time

print("app started")
time.sleep(30)
print("app finished")
```

然后执行：

```bash
python app.py
```

### 方式二：包装启动

```bash
pylinkagent-run python app.py
```

### 方式三：显式导入

```python
import os

os.environ["PYLINKAGENT_ENABLED"] = "true"
os.environ["MANAGEMENT_URL"] = "http://localhost:9999"
os.environ["APP_NAME"] = "my-python-app"

import pylinkagent
```

如果业务入口比较复杂，显式导入方式最容易先排除环境问题。确认链路打通后，再切回 `sitecustomize` 或 `pylinkagent-run`。

## 4. 最小烟测

下面这条命令用于验证当前安装环境能否自动加载、启动并关闭：

```bash
python -c "import pylinkagent; print(pylinkagent.is_running()); pylinkagent.shutdown(); print(pylinkagent.is_running())"
```

预期：

- 第一行输出 `True`
- 第二行输出 `False`

如果你不希望探针去连控制台和 ZK，可以在验证前先设置：

```bash
export ZK_ENABLED=false
export AUTO_REGISTER_APP=false
export SHADOW_ROUTING=false
```

Windows PowerShell 写法：

```powershell
$env:PYLINKAGENT_ENABLED="true"
$env:ZK_ENABLED="false"
$env:AUTO_REGISTER_APP="false"
$env:SHADOW_ROUTING="false"
python -c "import pylinkagent; print(pylinkagent.is_running()); pylinkagent.shutdown(); print(pylinkagent.is_running())"
```

## 5. 内网环境推荐验证顺序

### 第一步：只验静态挂载

先不要连控制台，也不要连 ZK，只验证探针是否能自动启动和停止。

Linux/macOS：

```bash
export PYLINKAGENT_ENABLED=true
export ZK_ENABLED=false
export AUTO_REGISTER_APP=false
export SHADOW_ROUTING=false
python -c "import pylinkagent; print(pylinkagent.is_running()); pylinkagent.shutdown(); print(pylinkagent.is_running())"
```

预期：

- 输出 `True`
- 输出 `False`

### 第二步：只验控制台 HTTP

先打开控制台地址，暂时仍然关闭 ZK 和影子路由：

```bash
export PYLINKAGENT_ENABLED=true
export MANAGEMENT_URL=http://<takin-web-host>:<port>
export APP_NAME=my-python-app
export AGENT_ID=my-python-agent
export ZK_ENABLED=false
export AUTO_REGISTER_APP=true
export SHADOW_ROUTING=false
python scripts/quick_verify.py
```

观察点：

- `ExternalAPI 初始化成功`
- 心跳请求无报错
- 控制台是否出现应用或探针安装信息

### 第三步：再验 ZooKeeper

```bash
export ZK_ENABLED=true
export REGISTER_NAME=zookeeper
export SIMULATOR_ZK_SERVERS=<zk1:2181,zk2:2181,zk3:2181>
export SIMULATOR_APP_NAME=my-python-app
python -c "import pylinkagent; import time; time.sleep(30)"
```

观察点：

- ZK 是否出现 `/config/log/pradar/client/<app>/<agentId>`
- 节点数据里是否包含 `agentLanguage=PYTHON`
- 节点是否为临时节点

### 第四步：最后验影子路由

等控制台和 ZK 基础链路稳定后，再打开：

```bash
export SHADOW_ROUTING=true
```

然后配合控制台下发影子库配置，进入 MySQL 隔离验证。

## 6. 常用环境变量

主链路：

- `PYLINKAGENT_ENABLED`
- `MANAGEMENT_URL`
- `APP_NAME`
- `AGENT_ID`
- `AUTO_REGISTER_APP`
- `CONFIG_FETCH_INTERVAL`
- `HEARTBEAT_INTERVAL`
- `COMMAND_POLL_INTERVAL`

请求头兼容字段：

- `USER_APP_KEY`
- `TENANT_APP_KEY`
- `USER_ID`
- `ENV_CODE`

ZooKeeper：

- `ZK_ENABLED`
- `REGISTER_NAME`
- `SIMULATOR_ZK_SERVERS`
- `SIMULATOR_APP_NAME`
- `SIMULATOR_AGENT_ID`
- `SIMULATOR_ENV_CODE`

## 7. 已知限制

- 命令拉取已接上，但安装、升级、卸载 handler 仍是占位实现
- `ConfigFetcher` 当前真正消费到运行时的仍以影子库配置为主
- `instrument_simulator`、`simulator_agent` 目前不是可用接入方式
- 控制台、ZK、影子路由的字段兼容仍在继续对齐 Java Agent
