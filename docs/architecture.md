# PyLinkAgent 当前架构

## 1. 主链路

当前可运行主链路全部收敛在 `pylinkagent/`：

```text
pylinkagent/
├─ auto_bootstrap.py
├─ bootstrap.py
├─ cli.py
├─ controller/
├─ pradar/
├─ shadow/
└─ zookeeper/
```

启动顺序：

1. 初始化 `ExternalAPI`
2. 应用注册
3. 初始化 ZooKeeper
4. 启动 `ConfigFetcher`
5. 把远程开关和白名单应用到运行时
6. 初始化影子路由
7. 启动 HTTP 心跳
8. 启动命令轮询

## 2. 控制台链路

核心组件：

- `pylinkagent/controller/external_api.py`
- `pylinkagent/controller/application_register.py`
- `pylinkagent/controller/heartbeat.py`
- `pylinkagent/controller/config_fetcher.py`
- `pylinkagent/controller/command_poller.py`

当前已经接通：

- 应用注册
- HTTP 心跳
- 命令拉取和结果回传骨架
- 影子库配置拉取
- 压测开关
- 白名单开关
- 远程调用白名单
- Redis / ES / Kafka / Shadow Job 配置拉取

当前还没闭环：

- 远程命令真实执行
- Mock / 黑名单 / forward 的完整策略执行

## 3. 标识规则

这是当前和 Java Agent 对齐最关键的一组规则。

### 3.1 HTTP 心跳

HTTP 心跳中的 `agentId` 使用 plain ID：

```text
10.0.0.1-1000
```

### 3.2 ZooKeeper

ZooKeeper 节点中的 `agentId` 使用 full ID：

```text
10.0.0.1-1000&fat:42:tenant-key
```

### 3.3 应用注册

应用注册 payload 当前会补齐：

- `applicationName`
- `applicationDesc`
- `agentId`
- `nodeKey`
- `machineIp`
- `hostName`
- `pid`
- `language`
- `frameworkName`
- `agentVersion`
- `pradarVersion`

## 4. 运行时配置链路

`ConfigFetcher` 会把远程配置灌入：

- `PradarSwitcher`
- `WhitelistManager`
- `ShadowConfigCenter`

当前已落地的运行时消费：

- 压测总开关
- 白名单开关
- URL / RPC / MQ / Cache Key 白名单
- 影子 DB
- 影子 Redis
- 影子 ES
- 影子 Kafka

## 5. 影子路由链路

当前拦截器入口：

- `mysql_interceptor.py`
- `sqlalchemy_interceptor.py`
- `redis_interceptor.py`
- `es_interceptor.py`
- `kafka_interceptor.py`
- `http_interceptor.py`

当前目标不是扩插件数量，而是先把这几条主链路做成可验证、可联调、可隔离。

## 6. 旧架构状态

下面这几条旧复刻线当前不属于主链路：

- `instrument_simulator/`
- `simulator_agent/`
- `instrument_modules/`

它们可以作为参考代码保留，但当前不要把它们当作“Python 版 Java simulator 已可运行”。
