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
├─ zookeeper/
└─ http_server_interceptor.py
```

启动顺序：

1. 初始化 `ExternalAPI`
2. 应用注册
3. 初始化 ZooKeeper
4. 启动 `ConfigFetcher`
5. 把远程开关和白名单应用到运行时
6. 初始化 HTTP 入口染色
7. 初始化影子路由
8. 启动 HTTP 心跳
9. 启动命令轮询

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

## 4. HTTP 入口染色链路

入口染色代码：

- `pylinkagent/http_server_interceptor.py`
- `pylinkagent/pradar/events.py`

当前行为：

- 启动时会尝试给 Flask 和 FastAPI 注册入口包装
- Flask 走 WSGI 包装
- FastAPI 走 ASGI 包装
- 请求进入时创建 `Pradar` 上下文
- 请求结束时落一条本地 `SpanEvent`，再清理 `Pradar` 上下文
- 支持从以下 header 识别压测流量：
  - `X-Pradar-Cluster-Test`
  - `Pradar-Cluster-Test`
  - `p-pradar-cluster-test`
  - `X-PyLinkAgent-Cluster-Test`
- 当前入口 span 会补齐：
  - `invoke_type=HTTP_SERVER`
  - `middleware_name=HTTP`
  - `request_summary`
  - `result_code`
  - `remote_ip/port`
  - `is_entry/is_server`

这条链路是当前把“控制台压测开关”和“MySQL 影子库切换”连起来的关键前提。

## 5. 本地 Trace 语义层

当前统一 trace 语义入口：

- `pylinkagent/pradar/context.py`
- `pylinkagent/pradar/events.py`
- `pylinkagent/pradar/pradar.py`

当前已经落地的最小统一模型：

- `InvokeContext.to_span_event()`
- `SpanEvent`
- 最近事件缓存 `get_event_store()`

当前用途：

- 单元测试回归
- `/debug/runtime` 诊断输出
- 为后续 collector / AMDB 上报保留统一导出层
- `SpanEventExporter` 批量 payload 组装
- `SpanUploader` 后台增量发送骨架

## 6. 运行时配置链路

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

## 7. 影子路由链路

当前拦截器入口：

- `mysql_interceptor.py`
- `sqlalchemy_interceptor.py`
- `redis_interceptor.py`
- `es_interceptor.py`
- `kafka_interceptor.py`
- `http_interceptor.py`

当前已经完成的关键修复：

- MySQL 压测流量下会同时改写 `db` 和 `database`
- SQLAlchemy URL 归一化已与 JDBC URL 对齐
- HTTP 客户端压测头注入支持反注册
- HTTP 客户端请求会生成本地 `HTTP_CLIENT` span
- 当前已覆盖 `requests`、`httpx.Client`、`httpx.AsyncClient`
- MySQL span 当前挂在 `cursor.execute/executemany`
- Redis span 当前挂在 `execute_command`

## 8. ZK Log Server 发现

当前接线位置：

- `pylinkagent/zookeeper/zk_log_server.py`
- `pylinkagent/controller/zk_integration.py`

当前行为：

- ZK 初始化成功后会尝试复用同一个 client 初始化 log server discovery
- heartbeat 启动时会同步启动 discovery
- `/debug/runtime` 会暴露：
  - `log_server_discovery_running`
  - `log_server_count`
  - `selected_log_server`
  - `log_servers`

当前边界：

- 只做到发现和选择
- 还没有按 Java collector 协议把 span 真正送到 log server

## 9. Draft Uploader

当前代码：

- `pylinkagent/pradar/uploader.py`

当前行为：

- 默认关闭，需显式设置 `PYLINKAGENT_SPAN_UPLOAD_ENABLED=true`
- 优先使用 `PYLINKAGENT_SPAN_UPLOAD_URL`
- 否则尝试使用 ZK 发现到的 `selected_log_server`
- 上传内容由 `PYLINKAGENT_SPAN_UPLOAD_PROTOCOL` 控制：
  - `python-span-draft-v1`
  - `java-collector-draft-v1`
  - `java-http-trace-log-draft-v1`
- 当前只解决：
  - 增量读取 span
  - 后台线程发送
  - 目标选择
  - 失败不阻塞业务

当前边界：

- 还不是 Java `TraceCollectorInvokeEncoder` 等价协议
- `java-collector-draft-v1` 只是字段映射更接近 Java，不代表已被现网 collector 验证通过
- `java-http-trace-log-draft-v1` 目前按 Java HTTP data pusher 的 `/log/link/upload` 方式发送 trace log 字节流，但仍未经过现网验证
- 还没有证明控制台/collector 可直接消费
- 现阶段只能作为联调辅助和协议验证骨架

## 10. 旧架构状态

下面这几条旧复刻线当前不属于主链路：

- `instrument_simulator/`
- `simulator_agent/`
- `instrument_modules/`

它们可以作为参考代码保留，但当前不要把它们当作“Python 版 Java simulator 已可运行”。
