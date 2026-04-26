# PyLinkAgent

PyLinkAgent 是一个面向 Python 应用的轻量探针，目标是尽量复用 Java LinkAgent 与 `Takin-web`、ZooKeeper 的核心交互模型，并优先完成以下闭环：

- Python 进程静态挂载
- 控制台应用注册与 HTTP 心跳
- ZooKeeper 在线节点注册
- 控制台远程配置拉取并进入运行时
- HTTP 入口染色
- 压测流量的数据隔离，优先覆盖 MySQL/Redis/ES/Kafka/HTTP

当前项目不再以“补齐 Java 94 个模块”为第一目标，优先级已经收敛到“先做出可接入、可观测、可隔离”的 Python 版本。

## 当前状态

已经落地：

- `sitecustomize` 自动加载
- `pylinkagent-run` 启动包装器
- `bootstrap` 主链路收敛
- Flask / FastAPI HTTP 入口染色
- `ExternalAPI` 控制台 HTTP 对接
- `ConfigFetcher`、`HeartbeatReporter`、`CommandPoller` 后台线程
- 压测总开关、白名单开关、远程调用白名单进入运行时
- ZooKeeper 心跳节点基础设施
- MySQL、SQLAlchemy、Redis、Elasticsearch、Kafka、HTTP 影子路由拦截器骨架
- 控制台关键字段对齐
  - HTTP 心跳使用 plain `agentId`
  - ZooKeeper 节点使用 full `agentId&envCode:userId:tenantAppKey`
  - 应用注册 payload 补齐 `agentId`、`nodeKey`、`machineIp`、`hostName`、`pid`、`language`

尚未闭环或只完成骨架：

- 远程命令安装、升级、卸载的真实执行
- Mock、黑名单、forward 等远程策略的完整消费
- Java Agent 级别的插件生态
- ZK client path / watch / 日志服务发现的完整集成
- 影子 Job 与更多中间件链路
- HTTP 入口染色到真实业务框架联调的内网验证

## 目录

当前应以 `pylinkagent/` 为主线：

```text
PyLinkAgent/
├─ pylinkagent/
│  ├─ auto_bootstrap.py
│  ├─ bootstrap.py
│  ├─ cli.py
│  ├─ controller/
│  ├─ pradar/
│  ├─ shadow/
│  ├─ zookeeper/
│  └─ http_server_interceptor.py
├─ docs/
├─ scripts/
├─ sitecustomize.py
└─ pyproject.toml
```

`instrument_simulator/`、`simulator_agent/`、`instrument_modules/` 这条旧复刻线当前不属于可运行主链路。

## 安装

```bash
cd PyLinkAgent
pip install -r requirements.txt
pip install -e .
```

## 启动方式

### 1. `sitecustomize` 自动加载

最接近 Java `-javaagent` 的体验。

```bash
export PYLINKAGENT_ENABLED=true
export MANAGEMENT_URL=http://localhost:9999
export APP_NAME=my-python-app
export AGENT_ID=10.0.0.1-1000
python app.py
```

### 2. `pylinkagent-run`

```bash
pylinkagent-run python app.py
```

### 3. 显式导入

```python
import os

os.environ["PYLINKAGENT_ENABLED"] = "true"
os.environ["MANAGEMENT_URL"] = "http://localhost:9999"
os.environ["APP_NAME"] = "my-python-app"

import pylinkagent
```

## 关键环境变量

控制台与启动：

- `PYLINKAGENT_ENABLED`
- `MANAGEMENT_URL`
- `APP_NAME`
- `AGENT_ID`
- `AUTO_REGISTER_APP`
- `HEARTBEAT_INTERVAL`
- `CONFIG_FETCH_INTERVAL`
- `COMMAND_POLL_INTERVAL`

控制台请求头兼容字段：

- `USER_APP_KEY`
- `TENANT_APP_KEY`
- `USER_ID`
- `ENV_CODE`
- `HTTP_MUST_HEADERS`

ZooKeeper：

- `ZK_ENABLED`
- `REGISTER_NAME`
- `SIMULATOR_ZK_SERVERS`
- `SIMULATOR_APP_NAME`
- `SIMULATOR_AGENT_ID`
- `SIMULATOR_ENV_CODE`
- `SIMULATOR_TENANT_ID`
- `SIMULATOR_USER_ID`
- `SIMULATOR_TENANT_APP_KEY`

影子路由：

- `SHADOW_ROUTING`

入口染色：

- `HTTP_SERVER_TRACING`

## 控制台与入口对齐规则

当前 Python 探针按下面规则与 Java Agent 保持关键一致：

- HTTP 心跳中的 `agentId` 使用 plain ID，例如 `10.0.0.1-1000`
- ZooKeeper 节点中的 `agentId` 使用 full ID，例如 `10.0.0.1-1000&fat:42:tenant-key`
- 应用注册描述会带上 `app`、`host`、`ip`、`pid`、`agentId`
- access status 上报中的 `nodeKey` 默认使用 `<appName>:<agentId>`
- ZooKeeper payload 除了 `jdkVersion`，还会补 `jdk=Python x.y.z`
- HTTP 入口当前支持识别这些压测标记：
  - `X-Pradar-Cluster-Test: 1`
  - `Pradar-Cluster-Test: 1`
  - `p-pradar-cluster-test: 1`
  - `X-PyLinkAgent-Cluster-Test: 1`

## 已完成验证

本地已经实际跑过：

- `py_compile`
- 自动加载烟测
- `pylinkagent-run` 注入验证
- 运行时配置同步测试
- 控制台字段对齐测试
- MySQL / SQLAlchemy 影子库切换测试
- HTTP 入口染色测试

可直接执行：

```bash
pytest tests/test_runtime_config_sync.py -q
pytest tests/test_control_plane_alignment.py -q
pytest tests/test_shadow_mysql_routing.py -q
pytest tests/test_http_ingress_tracing.py -q
```

当前覆盖：

- 配置拉取后进入 `PradarSwitcher`、`WhitelistManager`、`ShadowConfigCenter`
- 应用注册 payload 的关键字段
- HTTP 心跳使用 plain `agentId`
- ZooKeeper payload 使用 full `agentId`
- ZK payload 中的 `jdk/jdkVersion`
- MySQL 和 SQLAlchemy 在压测流量下改写到影子库连接参数
- WSGI / ASGI 入口能建立和清理 `Pradar` 上下文，并识别压测 header

## 文档索引

- [快速开始](docs/quickstart.md)
- [当前架构](docs/architecture.md)
- [验证方案](docs/verification.md)
- [ZooKeeper 集成现状](docs/ZOOKEEPER_INTEGRATION.md)
- [影子路由现状](docs/SHADOW_ROUTING_GUIDE.md)

## 当前建议

下一阶段优先级：

1. 继续对齐控制台注册、心跳、ZK 节点字段
2. 继续把 `HTTP 入口染色 -> MySQL 影子库切换` 做到真实框架联调
3. 再补 Redis、Kafka、ES 的联动配置与隔离
4. 最后再做真实命令执行和更多插件扩展
