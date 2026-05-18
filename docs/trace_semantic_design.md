# PyLinkAgent Trace 语义与中间件差异设计

这份设计文档的目标不是直接列一个“待开发清单”，而是先回答三个问题：

1. Java 探针真正给控制台提供的是什么数据语义
2. Python 运行时能在哪些位置稳定拿到这些语义
3. 哪些能力一期能做，哪些必须延后，否则会返工

## 当前实现进度

这份设计已经开始落代码，但当前只完成了一期的第一段：

- 已完成：
  - `SpanEvent` 统一语义模型
  - `InvokeContext -> SpanEvent` 导出层
  - 本地最近事件缓存
  - HTTP 入口 `HTTP_SERVER` span
  - HTTP 出口 `HTTP_CLIENT` span
  - MySQL execute 层 `DB` span
  - Redis execute 层 `CACHE` span
  - draft 版增量 Span uploader 骨架
  - Java `TraceCollectorInvokeEncoder` 风格的 draft 字段映射
- 尚未完成：
  - collector / log server 上报
  - `app_base_data` 基础指标上报

---

## 1. 背景

内网验证已经证明，Python 探针当前可以打通控制面：

- 静态挂载
- 应用注册 / 心跳
- ZK 在线节点
- 控制台影子配置拉取
- 压测 header 识别
- MySQL 影子库隔离

但控制台中以下模块仍然没有数据：

- 业务活动拓扑 / 类似拓扑图的链路节点展示
- 问题分析
- 压测明细
- 容量水位

这说明缺口已经不在控制面，而在数据面。

---

## 2. Java 探针的数据面模型

Java 探针不是“每个插件各自打一份日志”，而是：

1. 中间件插件在稳定埋点上产出统一的 `SpanRecord`
2. `Pradar` 把 `SpanRecord` 编码成 trace / monitor / collector 数据
3. collector / AMDB / Influx / MySQL 等后端消费这些统一数据
4. `Takin-web` 从这些后端拿数据，渲染拓扑、报告和诊断页面

关键代码：

- `module-pradar-core/.../SpanRecord.java`
- `module-pradar-core/.../TraceEncoder.java`
- `module-pradar-core/.../Pradar.java`
- `Takin-web/.../ApplicationEntranceClientImpl.java`
- `Takin-web/.../BaseServerDaoImpl.java`

### 2.1 Java 的统一语义字段

`SpanRecord` 及后续编码链路里，核心字段至少包括：

- `traceId`
- `invokeId` / `rpcId`
- `startTime`
- `cost`
- `agentId`
- `appName`
- `invokeType`
- `middlewareName`
- `serviceName`
- `methodName`
- `resultCode`
- `request`
- `response`
- `clusterTest`
- `upAppName`
- `remoteIp`
- `port`
- `callbackMsg`
- `tenantAppKey`
- `envCode`
- `userId`

这些字段最终不是只给“链路追踪页”使用，而是被多个模块复用：

- AMDB 拓扑
- `tro_pradar` 实时指标
- trace detail / 问题分析
- 压测明细

### 2.2 控制台实际依赖的数据源

按现有 `Takin-web` 代码，至少有三类：

1. AMDB 拓扑数据
- `/amdb/link/getLinkTopology`
- 用于业务活动拓扑、入口拓扑、节点关系展示

2. `tro_pradar`
- 用于 trace 明细、RT、TPS、错误数、调用类型等
- `BaseServerDaoImpl` 中大量查询直接依赖它

3. `app_base_data`
- 用于 CPU、内存、GC、网络等机器指标
- 容量水位、风险分析会读这部分

---

## 3. Python 与 Java 的本质差异

### 3.1 增强机制不同

Java：

- Bytecode instrumentation
- 稳定类 / 方法边界
- 插件能直接拿到 invocation 语义

Python：

- monkey patch / wrapper
- 客户端库差异更大
- 同步 / 异步 API 并存
- 很多 patch 点只能拿到“构造参数”，拿不到“每次调用语义”

因此 Python 不能简单照着 Java 的类名和插件名复刻。

### 3.2 Java 插件和 Python patch 的语义层级不同

当前 Python 的大多数实现更偏“路由改写层”，不是“trace 语义层”：

- `mysql_interceptor.py`：当前 patch `pymysql.connect()`
- `redis_interceptor.py`：当前 patch `redis.Redis.__init__()`
- `kafka_interceptor.py`：当前 patch `KafkaProducer/KafkaConsumer.__init__()`
- `http_interceptor.py`：当前主要做压测 header 透传

这对影子路由足够，但对控制台拓扑和报告不够，原因是：

- 构造连接不等于一次调用
- 拿到 host/port 不等于拿到 `serviceName/methodName/resultCode/cost`
- 只在构造期 patch，很难形成完整的调用边

### 3.3 Python 客户端生态更分裂

Java 很多中间件的“增强面”比较稳定，例如：

- Servlet Filter
- Dubbo Invoker
- MyBatis Session
- Kafka Producer/Consumer

Python 对应场景更分散：

- HTTP 入口：FastAPI / Flask / Starlette / Django / Gunicorn / Uvicorn
- HTTP 出口：requests / httpx / aiohttp
- MySQL：pymysql / mysqlclient / SQLAlchemy / asyncmy / aiomysql
- Redis：redis-py 单机 / cluster / pipeline
- Kafka：kafka-python / confluent-kafka
- ES：elasticsearch7 / elasticsearch8

如果不先定义统一语义模型，直接逐库 patch，最终得到的数据很难统一。

---

## 4. Python 版统一语义模型

在 Python 中，不应直接照搬 Java 的实现类，但应先定义等价的事件模型。

建议引入统一的 `SpanEvent` 概念，作为 Python trace/monitor/collector 的中间模型。

### 4.1 SpanEvent 必选字段

- `trace_id`
- `invoke_id`
- `parent_invoke_id`
- `start_time_ms`
- `end_time_ms`
- `cost_ms`
- `agent_id`
- `app_name`
- `invoke_type`
- `middleware_name`
- `service_name`
- `method_name`
- `result_code`
- `cluster_test`
- `is_entry`
- `is_server`
- `up_app_name`
- `remote_ip`
- `port`
- `tenant_app_key`
- `env_code`
- `user_id`

### 4.2 SpanEvent 可选字段

- `request_summary`
- `response_summary`
- `request_size`
- `response_size`
- `callback_msg`
- `attributes`
- `local_attributes`
- `error_message`
- `resource_name`
- `statement`
- `topic`
- `group_id`
- `db_name`
- `cache_key`

### 4.3 与当前 InvokeContext 的关系

当前 `pylinkagent/pradar/context.py` 已经有：

- `trace_id`
- `invoke_id`
- `app_name`
- `service_name`
- `method_name`
- `middleware_type`
- `cluster_test`
- `start_time/end_time/cost_time`

但还缺：

- `result_code`
- `remote_ip/port`
- `up_app_name`
- `is_entry/is_server`
- `request/response` 摘要
- `tenant/env/user`
- 面向 collector 的统一导出结构

所以正确做法不是另起一套 trace 上下文，而是在现有 `InvokeContext` 之上补统一导出层。

---

## 5. Python 稳定 patch 点设计

这里的原则是：

- 优先选择“调用发生时”的 patch 点，而不是“连接创建时”的 patch 点
- 优先选择“协议/语义稳定层”，而不是“具体实现细节层”
- 一期只选最稳定、最常见、最容易统一语义的点

### 5.1 HTTP 入口

目标语义：

- 入口 trace
- `is_entry=true`
- `is_server=true`
- `service_name=path`
- `method_name=HTTP method`
- header 提取压测标记 / trace 上下文

推荐 patch 点：

- FastAPI / Starlette ASGI app wrapper
- Flask WSGI app wrapper

当前状态：

- 已有 `http_server_interceptor.py`
- 适合继续扩展为 HTTP entry 语义采集的一期主入口

一期结论：

- 保留现有方案
- 在入口和返回时补全 SpanEvent 语义

### 5.2 HTTP 出口

目标语义：

- 下游调用边
- `middleware_name=HTTP`
- `service_name=host/path`
- `method_name=HTTP method`
- 请求结果码 / cost

推荐 patch 点：

- `requests.Session.request`
- `httpx.Client.send`
- `httpx.AsyncClient.send`

当前状态：

- 已有 `http_interceptor.py`
- 目前重点是压测 header 透传

一期结论：

- 复用现有 patch 点
- 增加 trace 事件采集，不重做 patch 入口

### 5.3 MySQL

目标语义：

- DB 调用边
- `middleware_name=MYSQL`
- `service_name=database` 或数据源标识
- `method_name=execute/executemany`
- SQL 摘要
- cost / result_code

不推荐的一期 patch 点：

- 只 patch `pymysql.connect()`

原因：

- 连接创建不是查询执行
- 控制台要的是调用边，不是连接边

推荐的一期 patch 点：

- `pymysql.cursors.Cursor.execute`
- `pymysql.cursors.Cursor.executemany`
- SQLAlchemy `Connection.execute` / `Session.execute`

当前状态：

- 只有 connect 层影子路由

一期结论：

- 保留 connect patch 继续负责影子路由
- 新增 execute 层 patch 负责 trace 语义

### 5.4 Redis

目标语义：

- cache 调用边
- `middleware_name=REDIS`
- `service_name=host:port/db`
- `method_name=command`
- key 摘要
- cost / result_code

不推荐的一期 patch 点：

- 只 patch `redis.Redis.__init__()`

推荐的一期 patch 点：

- `redis.Redis.execute_command`
- pipeline 执行入口

当前状态：

- 只有构造期影子路由

一期结论：

- 新增 execute 层 patch
- 构造期 patch 继续保留给影子路由使用

### 5.5 Kafka

目标语义：

- producer / consumer 调用边
- topic / group / bootstrap_servers
- send / poll / consume 结果

当前问题：

- `requirements.txt` 包含 `confluent-kafka`
- `pyproject.toml` 可选依赖是 `kafka-python`
- 当前实现写的是 `kafka-python`

这说明 Kafka 客户端标准还没统一。

一期结论：

- 不进入一期 trace 主链路
- 先在设计上只选定一个标准客户端
- 推荐先统一到 `kafka-python` 或明确切到 `confluent-kafka`，二选一后再做埋点

### 5.6 Elasticsearch

目标语义：

- search / index / bulk 调用边
- host / index / operation

当前问题：

- 版本差异大
- 客户端 API 变更频繁
- 对控制台首批价值低于 HTTP / DB / Redis

一期结论：

- 延后二期

---

## 6. 一期 / 二期范围

### 6.1 一期

目标：先让控制台开始出现“可消费的基础数据”。

范围：

- HTTP 入口 trace
- HTTP 出口 trace
- MySQL 执行层 trace
- Redis 执行层 trace
- 基础机器指标采集
- ZK log server 发现接入
- collector 上报最小闭环

一期暂不追求：

- Kafka 完整 trace
- ES 完整 trace
- MQ 消费链路完整闭环
- 与 Java 所有字段 100% 等价

### 6.2 二期

- Kafka trace
- Elasticsearch trace
- SQLAlchemy 深度覆盖
- MQ 消费端上下文恢复
- TraceNode / unknown node / 更多控制台诊断字段

### 6.3 三期

- 更完整插件生态
- 更接近 Java 的 log/collector/monitor 多通道能力
- 更深的 AMDB 兼容项

---

## 7. 控制台侧对应关系

按 `Takin-web` 当前实现，Python 探针补完后的目标应是：

### 7.1 业务活动拓扑

依赖：

- AMDB 的入口和拓扑数据

Python 一期需要提供：

- 至少 HTTP 入口 + HTTP 出口 + DB/Redis 边
- 可被 collector / AMDB 接受的统一 trace 数据

### 7.2 压测明细

依赖：

- `tro_pradar`
- traceId / event / callType / RT / TPS / errorCount

Python 一期需要提供：

- HTTP / DB / Redis 调用的 trace 和 monitor 数据

### 7.3 问题分析

依赖：

- trace detail
- machine metrics
- 部分 trace node / unknown node 数据

Python 一期需要提供：

- 基础 trace 明细
- 基础机器指标

### 7.4 容量水位

依赖：

- `app_base_data`

Python 一期需要提供：

- CPU / memory / GC / network / process 基础指标

---

## 8. 设计原则

接下来编码必须遵守这些原则：

1. 不直接按 Java 插件目录一比一复刻 Python 目录
2. 先统一 SpanEvent 语义，再做各库 patch
3. 路由 patch 和 trace patch 分层，不互相污染
4. 不在一期同时支持多个 Kafka 客户端
5. 不在一期同时做同步和异步 MySQL 的全覆盖
6. 优先保证控制台开始“有数据”，再追求字段完全等价

---

## 9. 编码顺序

建议按以下顺序推进：

1. 定义 `SpanEvent` / exporter / collector payload
2. 扩展 `InvokeContext`，补全导出字段
3. 改造 HTTP 入口 / 出口，产出统一 SpanEvent
4. 补 MySQL execute 层 trace
5. 补 Redis execute 层 trace
6. 接入 ZK log server 发现
7. 打通最小 collector 上报
8. 补 `app_base_data` 指标采集

---

## 10. 当前结论

当前 Python 探针最缺的不是“插件数量”，而是“统一语义模型”和“数据上报链路”。

如果不先把这两层设计清楚，直接照着 Java 名字补代码，会出现三个问题：

- patch 点选错，拿不到稳定语义
- collector 字段不统一，控制台还是吃不动
- Kafka / ES / Redis / MySQL 各做一套，最终返工合并

所以后续编码应严格按本文档推进。
