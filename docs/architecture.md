# PyLinkAgent 当前架构

本文档描述的是当前主链路，而不是历史规划。

## 1. 当前生效的模块边界

当前应该围绕 `pylinkagent/` 工作：

- `bootstrap.py`: 启动与关闭总入口
- `auto_bootstrap.py`: `PYLINKAGENT_ENABLED` 驱动的自动加载逻辑
- `cli.py`: `pylinkagent-run` 包装启动器
- `controller/`: 控制台 HTTP 对接、应用注册、后台线程
- `zookeeper/`: ZK 客户端、心跳、client path/log server 基础类
- `shadow/`: 影子配置中心、路由器、各类 interceptor
- `pradar/`: 上下文、开关、白名单、trace 标记基础类

## 2. 当前启动顺序

`pylinkagent.bootstrap()` 的主链路如下：

1. 初始化 `ExternalAPI`
2. 应用自动注册
3. 初始化 ZooKeeper
4. 启动 `ConfigFetcher`
5. 初始化影子路由并注册配置变更回调
6. 启动 HTTP 心跳线程
7. 启动命令轮询线程
8. 注册关闭钩子

这次收敛的关键调整是先启动 `ConfigFetcher`，再挂影子路由，避免影子配置回调注册时 `self._config_fetcher` 为空。

## 3. 自动加载方式

当前支持两条自动加载路径：

### `sitecustomize`

`sitecustomize.py` 会在解释器启动时自动执行，但只有在 `PYLINKAGENT_ENABLED=true` 时才会真正调用 `auto_bootstrap()`。

### `pylinkagent-run`

`pylinkagent-run` 会为目标进程注入 `PYLINKAGENT_ENABLED=true` 后再启动业务命令。

## 4. 控制面

当前 HTTP 控制面由 `pylinkagent/controller/external_api.py` 提供，主要覆盖：

- `/api/agent/heartbeat`
- `/api/agent/application/node/probe/operate`
- `/api/agent/application/node/probe/operateResult`
- `/api/application/center/app/info`
- `/api/link/ds/configs/pull`
- `/api/remote/call/configs/pull`
- `/api/link/ds/server/configs/pull`
- `/api/link/es/server/configs/pull`
- `/api/shadow/job/queryByAppName`
- `/api/agent/configs/shadow/consumer`
- `/api/application/center/app/switch/agent`
- `/api/global/switch/whitelist`

现状说明：

- 接口定义不等于闭环完成
- 目前真正跑进运行时主链路的包括：
  - 应用注册
  - HTTP 心跳
  - 命令拉取骨架
  - 影子库/Redis/ES/Kafka 配置加载
  - 压测总开关
  - 白名单开关
  - 远程调用白名单基础消费

## 5. ZooKeeper

当前 ZK 代码分为三层：

- `zk_client.py`: kazoo 客户端封装
- `zk_heartbeat.py`: 在线节点心跳
- `zk_client_path.py` / `zk_log_server.py`: client path 和日志服务发现基础类

当前集成状态：

- 已接入主链路的是 ZK 初始化与心跳
- `client path`、`watch`、`log server discovery` 仍未收敛为启动时默认闭环

默认在线路径已改为更接近 Java Agent 的：

```text
/config/log/pradar/client/{app}/{agentId}
```

## 6. 影子路由

当前拦截器列表：

- `MySQLShadowInterceptor`
- `SQLAlchemyShadowInterceptor`
- `RedisShadowInterceptor`
- `ESShadowInterceptor`
- `KafkaShadowInterceptor`
- `HTTPShadowInterceptor`

当前影子路由的核心问题不是“完全没有”，而是：

- 控制台拉到的影子库、Redis、ES、Kafka 配置已经开始灌入配置中心
- 但 Job、Mock、forward、更多中间件策略还没形成闭环
- 染色入口、全局开关、白名单等链路仍未和 Java Agent 等价

## 7. 旧框架的状态

以下目录目前不应被视为接入主线：

- `instrument_simulator/`
- `simulator_agent/`
- `instrument_modules/`

原因：

- 依赖缺失
- 导入链未闭合
- 未接入当前 `bootstrap` 主流程

后续如果继续做 Java Agent 等价能力，建议是在现有 `pylinkagent/` 主线上收敛，而不是继续扩旧框架分支。
