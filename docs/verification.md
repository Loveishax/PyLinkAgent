# PyLinkAgent 验证方案

这份文档分两部分：

1. 当前已经在本地实际验证过什么
2. 你拿到内网环境后，如何一步一步做全链路验证

## 1. 本地已完成验证

### 1.1 基础导入和自动加载

已通过：

- `import pylinkagent`
- `import pylinkagent.auto_bootstrap`
- `import pylinkagent.cli`
- `import sitecustomize`
- 自动加载启动和关闭烟测

### 1.2 运行时配置同步

命令：

```bash
python -m pytest tests/test_runtime_config_sync.py -q
```

覆盖：

- 压测总开关进入 `PradarSwitcher`
- 白名单开关进入 `PradarSwitcher` 和 `WhitelistManager`
- 远程调用白名单进入 `WhitelistManager`
- 影子 DB/Redis/ES/Kafka 配置进入 `ShadowConfigCenter`

### 1.3 控制台字段对齐

命令：

```bash
python -m pytest tests/test_control_plane_alignment.py -q
```

覆盖：

- 应用注册 payload 包含 `agentId`、`nodeKey`、`machineIp`、`hostName`、`pid`、`language`
- HTTP 心跳使用 plain `agentId`
- ZK 节点使用 full `agentId&envCode:userId:tenantAppKey`
- ZK payload 包含 `jdkVersion` 和 `jdk`

### 1.4 HTTP 入口染色

命令：

```bash
python -m pytest tests/test_http_ingress_tracing.py -q
```

覆盖：

- `X-Pradar-Cluster-Test`
- `Pradar-Cluster-Test`
- `p-pradar-cluster-test`
- `X-PyLinkAgent-Cluster-Test`
- WSGI 请求生命周期上下文
- ASGI 请求生命周期上下文

### 1.5 MySQL 影子路由

命令：

```bash
python -m pytest tests/test_shadow_mysql_routing.py -q
```

覆盖：

- `ShadowRouter.route_mysql()`
- `MySQLShadowInterceptor`
- `SQLAlchemyShadowInterceptor`

### 1.6 FastAPI + MySQL 真实数据库端到端

命令：

```bash
python -m pytest tests/test_fastapi_demo_e2e.py -q
```

本地实际结果已经确认：

- 普通请求写入 `pylinkagent_demo_biz`
- 带 `X-Pradar-Cluster-Test: 1` 的请求写入 `pylinkagent_demo_shadow`
- `GET /debug/runtime` 能看到当前探针运行状态、压测总开关和已加载影子库数量

这说明下面这段链路在本地已经打通：

`FastAPI 入口 -> 识别压测 header -> 建立 Pradar 上下文 -> pymysql.connect() 被改写 -> 写入 MySQL 影子库`

### 1.7 HTTP 下游压测标记透传

命令：

```bash
python -m pytest tests/test_http_shadow_propagation.py -q
```

覆盖：

- `requests` 下游调用自动注入 `X-Pradar-Cluster-Test: 1`
- `httpx` 同步和异步下游调用自动注入 `X-Pradar-Cluster-Test: 1`

## 2. 到哪一步可以去内网验证

就当前实现来说，你现在已经可以去内网验证完整主链路，但要分成两段理解：

### 2.1 本地已经闭环的部分

- 探针挂载
- HTTP 入口染色
- 压测流量识别
- MySQL 影子库切换

### 2.2 只能在内网联调验证的部分

- 控制台是否展示探针安装信息
- 控制台注册字段是否完全被页面消费
- ZK 节点是否按你们部署规范被消费
- 控制台下发的影子库配置是否与实际页面录入格式完全一致

所以结论是：

`现在已经具备进入内网做全链路验证的条件。`

## 3. 内网全链路验证步骤

目标链路：

`挂载 agent -> 控制台看到应用和探针 -> ZK 出现在线节点 -> 探针拉到影子库配置 -> 带压测标记请求写入影子库`

### 3.1 准备 FastAPI Demo

建议直接使用仓库里的 demo：

- [examples/fastapi_mysql_shadow_demo/app.py](../examples/fastapi_mysql_shadow_demo/app.py)
- [examples/fastapi_mysql_shadow_demo/init_demo_db.py](../examples/fastapi_mysql_shadow_demo/init_demo_db.py)

初始化数据库：

```bash
python examples/fastapi_mysql_shadow_demo/init_demo_db.py
```

默认会创建：

- `pylinkagent_demo_biz`
- `pylinkagent_demo_shadow`

两边都会创建 `demo_users` 表。

### 3.2 先做离线链路自检

如果你在内网第一天不想一上来就排查控制台和 ZK，先用本地离线模式：

```bash
export PYLINKAGENT_ENABLED=true
export AUTO_REGISTER_APP=false
export ZK_ENABLED=false
export SHADOW_ROUTING=true
export HTTP_SERVER_TRACING=true
export APP_NAME=fastapi-shadow-demo
export DEMO_LOCAL_SHADOW_CONFIG=true
export DEMO_LOCAL_CLUSTER_TEST_SWITCH=true
uvicorn examples.fastapi_mysql_shadow_demo.app:app --host 0.0.0.0 --port 8000
```

普通请求：

```bash
curl -X POST http://127.0.0.1:8000/users -H "Content-Type: application/json" -d "{\"name\":\"normal-user\"}"
```

压测请求：

```bash
curl -X POST http://127.0.0.1:8000/users -H "X-Pradar-Cluster-Test: 1" -H "Content-Type: application/json" -d "{\"name\":\"pressure-user\"}"
```

预期：

- 普通请求返回 `database=pylinkagent_demo_biz`
- 压测请求返回 `database=pylinkagent_demo_shadow`

### 3.3 切到控制台联调模式

把 demo 切到真正依赖控制台：

```bash
export PYLINKAGENT_ENABLED=true
export MANAGEMENT_URL=http://<takin-web-host>:<port>
export APP_NAME=fastapi-shadow-demo
export AGENT_ID=<plain-agent-id>
export USER_APP_KEY=<if-needed>
export TENANT_APP_KEY=<if-needed>
export USER_ID=<if-needed>
export ENV_CODE=<if-needed>
export AUTO_REGISTER_APP=true
export ZK_ENABLED=true
export REGISTER_NAME=zookeeper
export SIMULATOR_ZK_SERVERS=<zk1:2181,zk2:2181,zk3:2181>
export SIMULATOR_APP_NAME=fastapi-shadow-demo
export SIMULATOR_AGENT_ID=<plain-agent-id>
export SIMULATOR_ENV_CODE=<env-code>
export SIMULATOR_USER_ID=<user-id>
export SIMULATOR_TENANT_APP_KEY=<tenant-app-key>
export SHADOW_ROUTING=true
export HTTP_SERVER_TRACING=true
export DEMO_LOCAL_SHADOW_CONFIG=false
export DEMO_LOCAL_CLUSTER_TEST_SWITCH=false
uvicorn examples.fastapi_mysql_shadow_demo.app:app --host 0.0.0.0 --port 8000
```

### 3.4 控制台侧需要确认的配置

至少确认这几项：

- 应用名：`fastapi-shadow-demo`
- 压测总开关：打开
- 影子库配置：
  - 业务 JDBC URL：`jdbc:mysql://<mysql-host>:3306/pylinkagent_demo_biz`
  - 影子 JDBC URL：`jdbc:mysql://<mysql-host>:3306/pylinkagent_demo_shadow`
  - `dsType=0`

如果控制台有租户、应用 key、环境编码要求，也要和环境变量保持一致。

### 3.5 验证观察点

控制台：

- 是否出现应用
- 是否出现探针安装记录
- 心跳时间是否刷新

ZooKeeper：

- `/config/log/pradar/client/<appName>/<fullAgentId>` 是否存在
- 节点是否为临时节点
- 节点数据里是否有 `agentLanguage=PYTHON`

应用：

- 日志里是否出现 `Pradar 运行时配置已应用`
- 日志里是否出现 `影子配置已更新`
- 压测请求时是否出现 `MySQL rerouted to shadow DB`
- 访问 `GET /debug/runtime` 时，确认 `cluster_test_switch_enabled=true`，并检查 `db_mappings` 是否包含目标业务库
- 如果应用会再调用下游 HTTP 服务，检查下游是否收到 `X-Pradar-Cluster-Test: 1`

数据库：

- 普通请求只写业务库
- 压测请求只写影子库

## 4. 建议保留的证据

为了后续远程排查，建议保留：

- 启动命令
- 全量环境变量
- 完整启动日志
- 控制台页面截图
- ZK 节点路径和节点内容截图
- 普通请求和压测请求的返回结果
- 业务库 / 影子库实际数据截图

## 5. 诊断脚本

可以直接运行：

```bash
python scripts/diagnose.py
python scripts/diagnose.py http://127.0.0.1:8000
```

用途：

- 输出当前环境变量和控制台基础连通性
- 输出当前进程里的探针运行快照
- 如果传入应用地址，会直接抓取 `/debug/runtime`
