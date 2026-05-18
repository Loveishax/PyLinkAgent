# AI 交接与内网验证说明

这份文档给下一个继续接手的 AI 或内网联调同学使用，目标是让对方快速理解：

1. 这次 Python 探针改了什么
2. 这些改动的总体意图是什么
3. 需要在内网怎么验证
4. 验证后需要回传什么信息

## 1. 总体意图

本轮改动不是继续扩插件数量，而是把 `PyLinkAgent` 从“控制面可联通、影子路由可跑通”继续推进到“数据面开始具备与 Java Agent 对齐的基础能力”。

具体目标分三层：

1. 建立 Python 版统一 trace 语义层
2. 把 HTTP / MySQL / Redis 的调用事件落成本地 span
3. 按 Java 现有 HTTP data pusher 方式，准备一条最小可联调的 trace 上传链路

当前已经完成的是：

- 本地统一 `SpanEvent`
- HTTP 入口 `HTTP_SERVER` span
- HTTP 出口 `HTTP_CLIENT` span
- MySQL execute `DB` span
- Redis execute `CACHE` span
- ZK log server 发现接入主链路
- 运行时快照 `/debug/runtime` 可观察 span 与 log server 状态
- draft uploader 已具备两类导出模式：
  - `java-collector-draft-v1`
  - `java-http-trace-log-draft-v1`

当前最值得在内网验证的是：

`java-http-trace-log-draft-v1`

原因：

- 这是按 Java `HttpDataPusher` 的行为对齐出来的
- 走 HTTP `/log/link/upload`
- 头里带 `dataType/version/time/hostIp`
- body 是原始 trace log 字节流，不是 JSON span

## 2. 关键结论

从现有 Java 项目代码可以明确确认：

1. Java HTTP 推送路径是：
`/log/link/upload`

2. Java 会先探活：
`/health`

3. Java trace log 的 `dataType=1`

4. Java trace log 默认版本是：
`17`

5. Java HTTP 上传成功判定不是只看 `HTTP 200`，还要看响应 JSON 中：
`responseCode == CommandCode.SUCCESS`

因此，Python 探针当前推荐验证的协议模式不是 JSON body，而是：

`PYLINKAGENT_SPAN_UPLOAD_PROTOCOL=java-http-trace-log-draft-v1`

## 3. 本轮新增/改动的核心文件

这一节就是给 AI 和内网联调同学快速查“修改文件路径”的，不追求完整 diff，只列这次最关键的文件与意图。

下面列的是这轮最关键的文件和意图，不是完整 diff 清单。

### 3.1 统一 trace 语义

- [pylinkagent/pradar/events.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/pradar/events.py)
  - 新增 `SpanEvent`
  - 新增本地事件缓存
  - 新增 `event_id` 递增编号
  - 支持 `list_after(event_id)` 增量读取

- [pylinkagent/pradar/context.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/pradar/context.py)
  - 扩展 `InvokeContext`
  - 支持导出为 `SpanEvent`

- [pylinkagent/pradar/pradar.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/pradar/pradar.py)
  - `end_trace()` 自动记录已完成 span
  - 补充 request/response/resultCode/remote endpoint 等语义辅助方法

### 3.2 HTTP / DB / CACHE 事件

- [pylinkagent/http_server_interceptor.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/http_server_interceptor.py)
  - HTTP 入口染色
  - 结束请求时记录 `HTTP_SERVER` span

- [pylinkagent/shadow/http_interceptor.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/shadow/http_interceptor.py)
  - 下游 HTTP 透传压测头
  - 记录 `HTTP_CLIENT` span

- [pylinkagent/shadow/mysql_interceptor.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/shadow/mysql_interceptor.py)
  - 影子库连接切换
  - 在 `cursor.execute/executemany` 记录 `DB` span

- [pylinkagent/shadow/redis_interceptor.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/shadow/redis_interceptor.py)
  - 影子 Redis 路由
  - 在 `execute_command` 记录 `CACHE` span

### 3.3 导出与上传

- [pylinkagent/pradar/exporter.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/pradar/exporter.py)
  - 统一导出层
  - 支持三种协议：
    - `python-span-draft-v1`
    - `java-collector-draft-v1`
    - `java-http-trace-log-draft-v1`
  - 支持生成 Java trace log 风格文本行
  - 支持生成原始字节流

- [pylinkagent/pradar/uploader.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/pradar/uploader.py)
  - 新增后台 uploader
  - 默认关闭
  - 支持增量上传
  - 支持显式 URL 或 ZK 发现的 log server
  - `java-http-trace-log-draft-v1` 模式下：
    - 先调 `/health`
    - 再 POST `/log/link/upload`
    - 发送原始字节 body
    - 校验 `responseCode`

- [pylinkagent/bootstrap.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/bootstrap.py)
  - 接入 uploader 生命周期
  - 通过环境变量决定是否启用

### 3.4 ZK 与诊断

- [pylinkagent/controller/zk_integration.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/controller/zk_integration.py)
  - 接入 ZK log server discovery
  - 暴露选中的 log server 信息

- [pylinkagent/runtime_snapshot.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/pylinkagent/runtime_snapshot.py)
  - `/debug/runtime` 新增：
    - `recent_spans`
    - `log_servers`
    - `selected_log_server`
    - `span_export_preview`
    - `span_uploader`

- [scripts/diagnose.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/scripts/diagnose.py)
  - 增强联调诊断输出

## 4. 当前推荐的内网验证模式

推荐使用：

```bash
PYLINKAGENT_SPAN_UPLOAD_ENABLED=true
PYLINKAGENT_SPAN_UPLOAD_PROTOCOL=java-http-trace-log-draft-v1
```

如果 ZK 发现到的 log server 地址不可靠，优先显式指定：

```bash
PYLINKAGENT_SPAN_UPLOAD_URL=http://<log-server-host>:<port>/log/link/upload
```

这样能减少把问题混在“ZK 发现错地址”和“协议不兼容”之间。

## 5. 内网验证步骤

这一节就是标准“验证步骤”。建议严格按顺序执行，并保留每一步的输出。

### 5.1 启动前环境变量

至少配置这些：

```bash
export PYLINKAGENT_ENABLED=true
export MANAGEMENT_URL=http://<takin-web-host>:<port>
export APP_NAME=fastapi-shadow-demo
export AGENT_ID=<plain-agent-id>
export AUTO_REGISTER_APP=true
export ZK_ENABLED=true
export REGISTER_NAME=zookeeper
export SIMULATOR_ZK_SERVERS=<zk1:2181,zk2:2181,zk3:2181>
export SHADOW_ROUTING=true
export HTTP_SERVER_TRACING=true

export PYLINKAGENT_SPAN_UPLOAD_ENABLED=true
export PYLINKAGENT_SPAN_UPLOAD_PROTOCOL=java-http-trace-log-draft-v1
```

如果不用 ZK 发现 log server，补上：

```bash
export PYLINKAGENT_SPAN_UPLOAD_URL=http://<log-server-host>:<port>/log/link/upload
```

### 5.2 启动应用

建议先用 demo：

- [examples/fastapi_mysql_shadow_demo/app.py](/D:/soft/agent/LinkAgent-main/PyLinkAgent/examples/fastapi_mysql_shadow_demo/app.py)
- [examples/fastapi_mysql_shadow_demo/README.md](/D:/soft/agent/LinkAgent-main/PyLinkAgent/examples/fastapi_mysql_shadow_demo/README.md)

### 5.3 先看运行时快照

访问：

```text
GET /debug/runtime
```

重点看这些字段：

- `recent_spans`
- `log_server_discovery_running`
- `log_server_count`
- `selected_log_server`
- `span_export_preview`
- `span_uploader`

### 5.4 发送业务请求

先发普通请求，再发压测请求。

普通请求：

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"normal-user\"}"
```

压测请求：

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H "X-Pradar-Cluster-Test: 1" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"pressure-user\"}"
```

### 5.5 观察点

1. `/debug/runtime`
- `recent_spans` 是否出现：
  - `HTTP_SERVER`
  - `DB`
  - 如有下游 HTTP，则应有 `HTTP_CLIENT`
- `span_uploader.running`
- `span_uploader.last_target`
- `span_uploader.last_uploaded_count`
- `span_uploader.last_error`

2. log server
- `/health` 是否可访问
- `/log/link/upload` 是否收到请求
- 是否返回 `responseCode`

3. 控制台
- 应用是否在线
- 探针是否在线
- 心跳是否刷新

4. MySQL
- 普通流量是否写业务库
- 压测流量是否写影子库

## 6. 验证后必须回传的信息

这一节就是“需要回传的信息”。如果没有这些响应，后续很难继续精确收口协议。

这部分非常关键。如果联调失败，没有这些信息，后续只能猜。

### 6.1 必回传

1. `/debug/runtime` 的完整 JSON
2. `python scripts/diagnose.py` 输出
3. 启动命令和关键环境变量
4. 普通请求与压测请求的返回
5. 业务库与影子库查询结果

### 6.2 如果 uploader 开了，必须额外回传

1. `span_uploader.last_target`
2. `span_uploader.last_error`
3. `span_uploader.last_uploaded_count`
4. 如果服务端有访问日志：
   - 请求路径
   - 请求头
   - 返回码
   - 返回 body

### 6.3 如果服务端拒绝请求

必须带回：

1. 响应状态码
2. 响应 body
3. 服务端日志里的报错
4. 是否有 `responseCode`
5. 如果服务端其实不是按 HTTP data pusher 收：
   - 真实接口路径
   - 真实 header 要求
   - body 编码要求

## 7. 当前边界

当前不能误判成“已经完成”的部分：

1. `java-collector-draft-v1`
   - 只是字段映射接近 Java
   - 还没证明现网 collector 可消费

2. `java-http-trace-log-draft-v1`
   - 已按 Java HTTP pusher 方向对齐：
     - `/health`
     - `/log/link/upload`
     - `dataType=1`
     - `version=17`
     - `responseCode`
   - 但 trace log 文本内容是否已完全满足现网服务端，还要靠内网验证

3. monitor / 容量水位 / app_base_data
   - 这部分还没做
   - 现在主要推进的是 trace / 拓扑 / 压测明细方向

## 8. 下一步判断规则

内网验证回来后，按下面分支继续：

1. 如果 `/log/link/upload` 收到了请求，且 `responseCode` 正常，但控制台仍无数据
   - 继续查 body 内容与服务端消费链路

2. 如果 `/health` 或 `/log/link/upload` 不通
   - 先修地址或网络，不改协议

3. 如果服务端返回错误，且错误提示与格式相关
   - 继续收口 trace log 行格式

4. 如果服务端根本不是消费这条 HTTP 链路
   - 再切换到别的传输层实现

当前最重要的是：

`先证明 Python 探针能不能以 Java HTTP data pusher 的方式，被现网 log server 接收。`
