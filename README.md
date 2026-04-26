# PyLinkAgent

PyLinkAgent 是一个面向 Python 应用的轻量探针，目标是与 `Takin-web` 控制台和 ZooKeeper 保持可兼容的基础交互，并在压测流量进入后提供影子路由能力。

当前代码已经完成第一轮 P0 收敛，重点是把探针从“骨架代码”收敛到“可安装、可自动加载、可启动、可停止”的状态。现阶段优先目标不是追平 Java LinkAgent 的全部模块生态，而是先完成以下闭环：

- Python 进程静态挂载
- 控制台应用注册和 HTTP 心跳
- ZooKeeper 在线节点注册
- 影子库配置拉取与运行时接线
- MySQL/Redis/ES/Kafka/HTTP 的基础影子路由

## 当前状态

已落地：

- `sitecustomize` 自动加载入口
- `pylinkagent-run` 启动包装器
- `bootstrap` 主链路收敛
- `ExternalAPI` 基础控制台对接
- `ConfigFetcher`、`HeartbeatReporter`、`CommandPoller` 后台线程
- 压测总开关、白名单开关、远程调用白名单的运行时接线
- `ZooKeeper` 心跳基础设施
- `MySQL`、`SQLAlchemy`、`Redis`、`Elasticsearch`、`Kafka`、`HTTP` 拦截器骨架

尚未闭环或仅部分实现：

- 控制台远程配置的完整消费链路
  - 已接通：压测开关、白名单开关、远程调用白名单基础消费
  - 未闭环：Mock、forward、黑名单的完整策略执行
- 命令安装、升级、卸载的真实执行
- Java Agent 级别的模块生态
- 日志服务发现、client path/watch 的完整 ZK 集成
- `instrument_simulator` / `simulator_agent` 旧框架收敛

## 目录

当前应以 `pylinkagent/` 为主线：

```text
PyLinkAgent/
├── pylinkagent/
│   ├── auto_bootstrap.py
│   ├── bootstrap.py
│   ├── cli.py
│   ├── controller/
│   ├── pradar/
│   ├── shadow/
│   └── zookeeper/
├── docs/
├── scripts/
├── sitecustomize.py
└── pyproject.toml
```

`instrument_simulator/`、`simulator_agent/`、`instrument_modules/` 这条旧复刻线目前没有被收敛到可运行主链路中，不应作为当前接入方式。

## 安装

```bash
cd PyLinkAgent
pip install -r requirements.txt
pip install -e .
```

`pip install -e .` 会安装当前包，并把 `sitecustomize.py` 与 `pylinkagent-run` 一并暴露出来。

## 启动方式

### 1. `sitecustomize` 自动加载

这是最接近 Java `-javaagent` 的方式。安装包后，只要 Python 进程能导入当前环境中的 `sitecustomize`，并设置了 `PYLINKAGENT_ENABLED=true`，解释器启动时就会自动尝试拉起探针。

```bash
export PYLINKAGENT_ENABLED=true
export MANAGEMENT_URL=http://localhost:9999
export APP_NAME=my-python-app
export AGENT_ID=my-python-agent
python app.py
```

### 2. `pylinkagent-run` 包装启动

```bash
pylinkagent-run python app.py
```

这个命令会自动注入 `PYLINKAGENT_ENABLED=true`，适合不想改业务启动命令的场景。

### 3. 显式导入

```python
import os

os.environ["PYLINKAGENT_ENABLED"] = "true"
os.environ["MANAGEMENT_URL"] = "http://localhost:9999"
os.environ["APP_NAME"] = "my-python-app"

import pylinkagent
```

`pylinkagent.__init__` 会调用 `auto_bootstrap()`。如果只想手动控制，也可以直接调用 `pylinkagent.bootstrap()`。

## 关键环境变量

控制台和主链路：

- `PYLINKAGENT_ENABLED`: 是否允许自动加载，`true/false`
- `MANAGEMENT_URL`: 控制台地址，默认 `http://localhost:9999`
- `APP_NAME`: 应用名，默认 `default-app`
- `AGENT_ID`: 探针实例 ID，默认 `pylinkagent-<pid>`
- `AUTO_REGISTER_APP`: 是否自动注册应用，默认 `true`
- `HEARTBEAT_INTERVAL`: HTTP 心跳间隔秒数，默认 `60`
- `CONFIG_FETCH_INTERVAL`: 配置拉取间隔秒数，默认 `60`
- `COMMAND_POLL_INTERVAL`: 命令轮询间隔秒数，默认 `30`

控制台请求头兼容字段：

- `USER_APP_KEY`
- `TENANT_APP_KEY`
- `USER_ID`
- `ENV_CODE`
- `HTTP_MUST_HEADERS`

ZooKeeper：

- `ZK_ENABLED`: 是否启用 ZK，默认 `true`
- `REGISTER_NAME`: 默认 `zookeeper`
- `SIMULATOR_ZK_SERVERS`
- `SIMULATOR_APP_NAME`
- `SIMULATOR_AGENT_ID`
- `SIMULATOR_ENV_CODE`
- `SIMULATOR_TENANT_ID`
- `SIMULATOR_USER_ID`
- `SIMULATOR_TENANT_APP_KEY`

影子路由：

- `SHADOW_ROUTING`: 是否启用影子路由，默认 `true`

## 已确认的本地修改

这一轮已经写入本地文件的核心改动如下：

- `pyproject.toml`
  - 新增 `pylinkagent-run`
  - 打包范围改为 `pylinkagent*`
  - 暴露 `sitecustomize.py`
- `sitecustomize.py`
  - 新增解释器启动自动加载钩子
- `pylinkagent/auto_bootstrap.py`
  - 新增环境变量驱动的自动启动逻辑
- `pylinkagent/cli.py`
  - 新增包装启动器
- `pylinkagent/bootstrap.py`
  - 调整启动顺序
  - 保留实际 interceptor 实例并正确反注册
  - 接入 `SQLAlchemy` 拦截器
  - 启动和停止链路收敛
- `pylinkagent/controller/config_fetcher.py`
- `pylinkagent/controller/heartbeat.py`
- `pylinkagent/controller/command_poller.py`
  - 后台线程使用 `Event.wait()`，停止不再被初始睡眠卡住
- `pylinkagent/controller/external_api.py`
  - 补齐 `agent_version` / `simulator_version`
- `pylinkagent/zookeeper/config.py`
  - 在线节点默认路径调整为 `/config/log/pradar/client`
  - 修复 Python 版本字段生成

## 已完成验证

已实际验证：

- 关键文件 `py_compile` 通过
- `import pylinkagent` 在 `PYLINKAGENT_ENABLED=true` 下会自动尝试拉起探针
- `pylinkagent.shutdown()` 能正常关闭后台线程
- `pylinkagent-run python -c ...` 会注入 `PYLINKAGENT_ENABLED=true`
- 在本地无控制台服务时，自动加载启动耗时约 `0.66s`，不会因为同步拉配置而长时间卡住

详细验证步骤见 [docs/verification.md](docs/verification.md)。

## 文档索引

- [快速开始](docs/quickstart.md)
- [当前架构](docs/architecture.md)
- [验证方案](docs/verification.md)
- [ZooKeeper 集成现状](docs/ZOOKEEPER_INTEGRATION.md)
- [影子路由现状](docs/SHADOW_ROUTING_GUIDE.md)

## 当前建议

如果目标是先做出“Python 版本的可接入 LinkAgent”，后续优先级建议是：

1. 对齐控制台注册、心跳、ZK 节点字段
2. 把影子库、白名单、全局开关真正灌进运行时
3. 先闭合 `HTTP 入口染色 -> MySQL 影子库切换`
4. 再扩 Redis、Kafka、ES 的联动配置
