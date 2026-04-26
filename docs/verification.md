# PyLinkAgent 验证方案

本文档只记录两类内容：

- 已经在当前环境实际执行过的验证
- 你后续放到内网环境时，建议按什么顺序验证

## 1. 已完成的本地验证

### 1.1 语法与导入

已通过：

- `py_compile`
- `import pylinkagent`
- `import pylinkagent.auto_bootstrap`
- `import pylinkagent.cli`
- `import sitecustomize`

### 1.2 自动加载烟测

测试环境：

```bash
export PYLINKAGENT_ENABLED=true
export ZK_ENABLED=false
export AUTO_REGISTER_APP=false
export SHADOW_ROUTING=false
```

验证脚本：

```bash
python -c "import pylinkagent; print(pylinkagent.is_running()); pylinkagent.shutdown(); print(pylinkagent.is_running())"
```

已确认：

- `import pylinkagent` 会自动尝试启动探针
- `shutdown()` 能正常停掉后台线程
- 本地无控制台服务时，启动不会被初始同步拉配置长时间卡住

### 1.3 CLI 注入验证

```bash
pylinkagent-run python -c "import os; print(os.getenv('PYLINKAGENT_ENABLED'))"
```

预期输出：

```text
true
```

### 1.4 运行时配置同步测试

```bash
pytest tests/test_runtime_config_sync.py -q
```

当前已通过，覆盖：

- 压测总开关进入 `PradarSwitcher`
- 白名单开关进入 `PradarSwitcher` 和 `WhitelistManager`
- 远程调用白名单进入 `WhitelistManager`
- 影子 DB/Redis/ES/Kafka 配置进入 `ShadowConfigCenter`

### 1.5 控制台字段对齐测试

```bash
pytest tests/test_control_plane_alignment.py -q
```

当前已通过，覆盖：

- 应用注册 payload 包含 `agentId`、`nodeKey`、`machineIp`、`hostName`、`pid`、`language`
- HTTP 心跳使用 plain `agentId`
- ZK 节点 payload 使用 full `agentId&envCode:userId:tenantAppKey`
- ZK payload 同时包含 `jdkVersion` 和 `jdk`

### 1.6 MySQL 影子库路由测试

```bash
pytest tests/test_shadow_mysql_routing.py -q
```

当前已通过，覆盖：

- `ShadowRouter.route_mysql()` 在压测流量下返回影子库连接参数
- `MySQLShadowInterceptor` 会把 `db/database` 一并改写到影子库
- `SQLAlchemyShadowInterceptor` 会把 engine URL 改写到影子库

## 2. 内网联调建议顺序

建议严格按下面顺序走，避免多条链路同时排错。

### 2.1 静态挂载验证

目标：

- 包已安装
- `sitecustomize` 生效
- 进程启动时自动加载探针

建议最小命令：

```bash
python -c "import pylinkagent; print(pylinkagent.is_running())"
```

观察点：

- 进程日志里是否出现 `PyLinkAgent 启动中`
- `is_running()` 是否输出 `True`

### 2.2 控制台 HTTP 对接验证

目标：

- `MANAGEMENT_URL` 可达
- 应用注册成功
- 心跳请求正常发出

建议先设置：

```bash
export PYLINKAGENT_ENABLED=true
export MANAGEMENT_URL=http://<takin-web-host>:<port>
export APP_NAME=<python-app-name>
export AGENT_ID=<plain-agent-id>
export USER_APP_KEY=<if-needed>
export TENANT_APP_KEY=<if-needed>
export USER_ID=<if-needed>
export ENV_CODE=<if-needed>
```

建议观察：

- 控制台应用列表中是否出现应用
- 控制台探针安装信息中是否出现该实例
- 最近一次心跳时间是否更新
- 本地日志是否出现注册成功或心跳成功信息

重点核对字段：

- `applicationName`
- `agentId`
- `nodeKey`
- `machineIp`
- `hostName`
- `pid`
- `agentVersion`
- `pradarVersion`

### 2.3 ZooKeeper 在线节点验证

目标：

- 能连接到 ZK
- 在线节点创建成功
- 节点数据字段符合预期

建议先设置：

```bash
export ZK_ENABLED=true
export REGISTER_NAME=zookeeper
export SIMULATOR_ZK_SERVERS=<zk-hosts>
export SIMULATOR_APP_NAME=<python-app-name>
export SIMULATOR_AGENT_ID=<plain-agent-id>
export SIMULATOR_ENV_CODE=<env-code>
export SIMULATOR_USER_ID=<user-id>
export SIMULATOR_TENANT_APP_KEY=<tenant-app-key>
```

重点核对节点路径：

```text
/config/log/pradar/client/<appName>/<fullAgentId>
```

其中：

- `plainAgentId` 示例：`10.0.0.1-1000`
- `fullAgentId` 示例：`10.0.0.1-1000&fat:42:tenant-key`

重点核对节点数据字段：

- `agentId`
- `agentLanguage`
- `agentVersion`
- `simulatorVersion`
- `address`
- `host`
- `name`
- `pid`
- `envCode`
- `tenantAppKey`
- `userId`
- `jdkVersion`
- `jdk`

附加检查：

- 节点是否为临时节点
- Python 进程退出后节点是否自动消失

### 2.4 远程配置联动验证

目标：

- 控制台下发开关和影子配置后，Python 运行时状态发生变化

建议优先验证：

1. 压测总开关
2. 白名单开关
3. 影子库配置

建议观察：

- 本地日志中是否出现 `Pradar 运行时配置已应用`
- 本地日志中是否出现 `影子配置已更新`
- 控制台侧配置变更后，下一次轮询是否生效

### 2.5 MySQL 影子库隔离验证

这是当前最关键的业务验证项。

目标：

- 普通流量仍访问业务库
- 压测流量切换到影子库

建议最小验证方法：

1. 准备一组业务库和影子库，表结构一致
2. 控制台下发影子库配置
3. 发两组请求

普通流量：

- 不带压测标记
- 预期写入业务库

压测流量：

- 带压测标记
- 当前可先用临时 header，例如 `X-PyLinkAgent-Cluster-Test: 1`
- 预期写入影子库

建议记录：

- 请求 header
- 应用日志
- SQL 实际落库结果
- 控制台影子库配置截图

如果先只想做代码级冒烟，可先在本地跑：

```bash
pytest tests/test_shadow_mysql_routing.py -q
```

## 3. 当前不能视为“已完成验证”的内容

以下内容即使代码里有类或骨架，也不能算已经联调完成：

- 真实命令安装、升级、卸载
- ZK client path / watch / 日志服务发现完整链路
- Java Agent 等价的全量插件生态
- Mock / 黑名单 / forward 完整执行链路
- 全量端到端压测数据隔离

## 4. 建议你在内网环境保留的证据

为了后续远程排查，建议至少保存这些信息：

- Python 版本
- 安装方式：`pip install -e .` 还是离线 wheel
- 启动方式：`sitecustomize` / `pylinkagent-run` / 显式导入
- `MANAGEMENT_URL`
- `APP_NAME`
- `AGENT_ID`
- `SIMULATOR_ZK_SERVERS`
- 完整启动日志
- 控制台页面截图
- ZK 节点路径和节点内容截图
- 影子库实际写入结果
