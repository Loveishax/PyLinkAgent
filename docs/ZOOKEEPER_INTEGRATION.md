# ZooKeeper 集成现状

## 1. 当前目标

Python 探针在 ZK 侧当前优先保证两件事：

- 应用启动后能创建在线节点
- 节点字段风格尽量接近 Java Agent，便于控制台和排障工具识别

## 2. 当前已接通

代码位置：

- `pylinkagent/zookeeper/config.py`
- `pylinkagent/zookeeper/zk_client.py`
- `pylinkagent/zookeeper/zk_heartbeat.py`
- `pylinkagent/zookeeper/zk_client_path.py`
- `pylinkagent/controller/zk_integration.py`

当前已实现：

- Kazoo 客户端封装
- ZK 连接与重连监听
- 在线节点创建
- 节点数据刷新
- 断连后的基础恢复逻辑
- 正常退出时主动删除在线节点并关闭 ZK 会话
- `SIGTERM`、`SIGINT`、`SIGBREAK`、`SIGHUP` 关闭钩子
- `session timeout` / `connection timeout` 环境变量配置

## 3. 节点路径规则

当前默认在线节点路径：

```text
/config/log/pradar/client/<appName>/<fullAgentId>
```

其中：

- `<appName>` 来自 `APP_NAME` 或 `SIMULATOR_APP_NAME`
- `<fullAgentId>` 格式为 `plainAgentId&envCode:userId:tenantAppKey`

示例：

```text
/config/log/pradar/client/demo-app/10.0.0.1-1000&fat:42:tenant-key
```

## 4. 字段规则

当前 ZK payload 重点字段：

- `agentId`
- `agentLanguage=PYTHON`
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

其中：

- `name` 当前已改为应用名，而不是工作目录名
- `jdk` 和 `jdkVersion` 当前都会写成 `Python x.y.z`

## 5. 节点回收行为

当前在线节点使用临时节点，行为与 Java Agent 一致：

- 正常退出：探针执行 `shutdown`，主动删除节点。
- 可捕获终止信号：探针会进入同一条关闭链路，尽量立即删除节点。
- 强制终止：如果进程无法执行清理代码，节点依赖 ZK 会话超时回收。

可用环境变量：

- `SIMULATOR_ZK_SESSION_TIMEOUT_MS`
- `SIMULATOR_ZK_CONNECTION_TIMEOUT_MS`
- `ZK_SESSION_TIMEOUT_MS`
- `ZK_CONNECTION_TIMEOUT_MS`

建议内网联调时把 `SIMULATOR_ZK_SESSION_TIMEOUT_MS` 设到 `10000-15000`，方便观察强制杀进程后的节点回收。

## 6. 与 Java Agent 的关系

当前已经对齐的关键点：

- `plainAgentId` 和 `fullAgentId` 的拆分规则
- `agentLanguage`
- `envCode/userId/tenantAppKey`
- `jdk/jdkVersion`
- log server discovery 已接入主启动链路，并可在 `/debug/runtime` 观察

当前还没完全对齐的部分：

- client path / watch 的完整主流程集成
- 日志服务发现后的真实数据推送
- 更完整的状态码、错误码和模块协同信息

## 7. 当前结论

不能再说“Python 探针没有 ZK 实现”，因为基础设施和在线节点链路已经有了。

但也不能说“已经完全对齐 Java Agent”，因为当前主要是在线节点和基础字段收敛，完整的 client path/watch/log server 体系还没有闭环。
