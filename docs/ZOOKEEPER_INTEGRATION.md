# PyLinkAgent ZooKeeper 集成现状

这份文档只描述当前代码现状，不再使用“已经与 Java 完整对齐”这类表述。

## 1. 当前已有能力

代码位置：

- `pylinkagent/zookeeper/config.py`
- `pylinkagent/zookeeper/zk_client.py`
- `pylinkagent/zookeeper/zk_heartbeat.py`
- `pylinkagent/zookeeper/zk_client_path.py`
- `pylinkagent/zookeeper/zk_log_server.py`
- `pylinkagent/controller/zk_integration.py`

当前已具备：

- ZK 配置加载
- kazoo 客户端封装
- Agent 在线心跳节点
- 基础 heartbeat data 组装
- client path 和 log server discovery 的基础类

## 2. 当前主链路实际接入情况

`bootstrap()` 默认会尝试初始化 ZK：

1. 读取 `ZK_ENABLED`
2. 调用 `initialize_zk()`
3. 启动在线节点相关逻辑

现阶段真正接入主链路的是“ZK 初始化 + 心跳基础能力”。

以下能力仍不能视为已经闭环：

- `client path` 注册与 watch
- 日志服务发现接入上传链路
- 完整 Pradar 注册协同
- Java Agent 级别的状态字段完全对齐

## 3. 默认路径

当前默认值已经调整为：

```text
status_base_path=/config/log/pradar/client
client_base_path=/config/log/pradar/client
server_base_path=/config/log/pradar/server
```

说明：

- 这是为了让 Python 探针的在线节点默认更接近 Java Agent 的可见路径
- 代码里 `get_status_path()` 与 `get_client_path()` 当前都会落到 `/config/log/pradar/client/...`

## 4. 关键环境变量

- `ZK_ENABLED`
- `REGISTER_NAME`
- `SIMULATOR_ZK_SERVERS`
- `SIMULATOR_APP_NAME`
- `SIMULATOR_AGENT_ID`
- `SIMULATOR_ENV_CODE`
- `SIMULATOR_TENANT_ID`
- `SIMULATOR_USER_ID`
- `SIMULATOR_TENANT_APP_KEY`
- `SIMULATOR_AGENT_VERSION`
- `SIMULATOR_VERSION`
- `MANAGEMENT_URL`

## 5. 心跳数据

`ZkConfig.to_heartbeat_data()` 当前会生成类似字段：

- `address`
- `host`
- `name`
- `pid`
- `agentId`
- `agentLanguage=PYTHON`
- `agentVersion`
- `simulatorVersion`
- `agentStatus`
- `errorCode`
- `errorMsg`
- `jvmArgs`
- `jdkVersion`
- `tenantAppKey`
- `envCode`
- `userId`
- `service`
- `port`

这部分已经在向 Java Agent 对齐，但还没有经过真实控制台与 ZK 端到端验收。

## 6. 当前结论

可以说：

- Python 侧已经不再是“完全没有 ZK”
- 当前已具备基础 ZK 基础设施和在线节点能力

不能说：

- 已与 Java Agent 的 ZK 交互完全等价
- 控制台、client path、日志发现、配置 watch 已全部闭环
