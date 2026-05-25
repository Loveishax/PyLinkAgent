# 项目背景与接手说明

这份文档的目标不是记录某一次小改动，而是让下一个 AI 或研发同学在接手时，先理解：

1. 这个项目为什么存在
2. 当前真正要做的事情是什么
3. 它和哪些项目强相关
4. 关键交互流程在哪里
5. 当前已经完成什么、卡在哪里、下一步该怎么推进

如果只能先读一份文档，优先读这份。

## 1. 项目背景

当前工作目录的核心项目有两条线：

- `D:\soft\agent\LinkAgent-main`
  - Java 探针主项目，也是 Python 版本的参考基线
- `D:\soft\agent\LinkAgent-main\PyLinkAgent`
  - 当前正在推进的 Python 探针项目

用户的真实目标不是做一个“Python APM demo”，而是尽量让 Python 探针在以下能力上接近 Java LinkAgent：

1. 挂载到 Python 项目上，尽量接近 Java `-javaagent` 的静态注入体验
2. 与控制台交互，让控制台能看到应用、探针、心跳、ZooKeeper 在线状态
3. 从控制台拉取压测配置，尤其是影子库配置
4. 识别压测流量，把压测写请求隔离到影子库
5. 进一步让控制台上的链路拓扑、压测明细、问题分析、容量水位等模块开始有数据

这意味着项目分成两条主线：

- 控制面：注册、心跳、配置拉取、ZK 节点
- 数据面：trace、metrics、拓扑、日志/collector 上报

当前控制面已经基本打通，数据面只做到了“本地语义层 + draft 上传骨架”，还没有证明被现网完整消费。

## 2. 当前项目定位

不要把 `PyLinkAgent` 当成“已经完成的 Java LinkAgent 复刻版”。

更准确的定位是：

`PyLinkAgent 当前是一个以 Python 静态挂载、控制台联通、影子路由和 trace 数据面起步为目标的探针项目。`

当前优先级不是“补齐 94 个 Java 插件”，而是先把这条主链路做实：

`挂载探针 -> 控制台看到探针 -> 拉到影子配置 -> 识别压测流量 -> 写入 MySQL 影子库 -> 尝试把 trace 数据送到现网可消费链路`

## 3. 与哪些项目有核心交互

### 3.1 当前主项目

- `D:\soft\agent\LinkAgent-main\PyLinkAgent`
  - 当前正在修改的 Python 探针项目

### 3.2 Java 参考基线

- `D:\soft\agent\LinkAgent-main`
  - Java LinkAgent 主仓库
  - Python 项目的控制面接口、影子路由语义、trace/collector 逻辑都要参考这里

### 3.3 控制台主交互项目

- `D:\soft\agent\Takin-web`
  - 当前最重要的控制台项目
  - 应用注册、配置中心、拓扑、压测明细、容量水位等都主要从这里判断

### 3.4 企业版相关项目

- `D:\soft\agent\takin-ee-web`
  - 需要重点关注 trace、fast-debug、EE agent URL 常量等
  - 它不是 P0 控制面的第一入口，但对后续 trace/日志数据消费很关键

### 3.5 Agent 管理相关项目

- `D:\soft\agent\agent-management`
  - 目前不是第一优先级
  - 可作为 agent 规格、collector-agent / trace-agent 定义的参考

## 4. Python 项目当前主线架构

### 4.1 应该优先阅读的目录

- `PyLinkAgent/pylinkagent/`
  - 当前真正的主线实现
- `PyLinkAgent/examples/fastapi_mysql_shadow_demo/`
  - 当前最重要的联调 demo
- `PyLinkAgent/docs/`
  - 已有的内网验证、trace 设计、AI 交接文档

### 4.2 不应该作为当前主线继续推进的目录

- `PyLinkAgent/instrument_simulator/`
- `PyLinkAgent/simulator_agent/`

这两套目录代表旧的“模拟 Java simulator 框架”的尝试，但当前主线已经明确转向 `pylinkagent/`。
后续如果继续开发，应优先收敛在 `pylinkagent/`，不要再把主要精力放到 `instrument_simulator` 和 `simulator_agent` 上。

### 4.3 当前 Python 主线关键文件

- `PyLinkAgent/pylinkagent/bootstrap.py`
  - 总启动链路，决定控制面、ZK、影子路由、HTTP 入口、span uploader 是否被拉起
- `PyLinkAgent/sitecustomize.py`
  - 静态挂载入口之一，最接近 Java `-javaagent`
- `PyLinkAgent/pylinkagent/auto_bootstrap.py`
  - 自动启动包装
- `PyLinkAgent/pylinkagent/cli.py`
  - `pylinkagent-run` 命令入口

控制面关键文件：

- `PyLinkAgent/pylinkagent/controller/external_api.py`
- `PyLinkAgent/pylinkagent/controller/application_register.py`
- `PyLinkAgent/pylinkagent/controller/heartbeat.py`
- `PyLinkAgent/pylinkagent/controller/config_fetcher.py`
- `PyLinkAgent/pylinkagent/controller/command_poller.py`

ZK 关键文件：

- `PyLinkAgent/pylinkagent/controller/zk_integration.py`
- `PyLinkAgent/pylinkagent/zookeeper/zk_client.py`
- `PyLinkAgent/pylinkagent/zookeeper/zk_heartbeat.py`
- `PyLinkAgent/pylinkagent/zookeeper/zk_log_server.py`
- `PyLinkAgent/pylinkagent/zookeeper/config.py`

影子路由关键文件：

- `PyLinkAgent/pylinkagent/shadow/config_center.py`
- `PyLinkAgent/pylinkagent/shadow/mysql_interceptor.py`
- `PyLinkAgent/pylinkagent/shadow/redis_interceptor.py`
- `PyLinkAgent/pylinkagent/shadow/http_interceptor.py`

数据面关键文件：

- `PyLinkAgent/pylinkagent/pradar/context.py`
- `PyLinkAgent/pylinkagent/pradar/pradar.py`
- `PyLinkAgent/pylinkagent/pradar/events.py`
- `PyLinkAgent/pylinkagent/pradar/exporter.py`
- `PyLinkAgent/pylinkagent/pradar/uploader.py`
- `PyLinkAgent/pylinkagent/http_server_interceptor.py`
- `PyLinkAgent/pylinkagent/runtime_snapshot.py`

诊断与验证：

- `PyLinkAgent/scripts/diagnose.py`
- `PyLinkAgent/examples/fastapi_mysql_shadow_demo/app.py`
- `PyLinkAgent/tests/`

## 5. 当前已完成的关键能力

### 5.1 控制面

已经具备：

- `sitecustomize` 自动挂载
- `pylinkagent-run` 启动包装
- 控制台 HTTP 注册/心跳骨架
- ZK 在线节点创建
- 控制台影子库、白名单、开关等配置拉取并进入运行时

### 5.2 影子路由

已经具备：

- HTTP 入口识别压测流量
- MySQL/SQLAlchemy 影子库切换
- Redis/ES/Kafka/HTTP 的基础影子路由骨架

### 5.3 本地 trace 语义层

已经具备：

- 统一 `SpanEvent` 模型
- HTTP 入口 `HTTP_SERVER` span
- HTTP 出口 `HTTP_CLIENT` span
- MySQL execute `DB` span
- Redis execute `CACHE` span
- `/debug/runtime` 查看最近 span、log server、uploader 状态

### 5.4 draft 上传链路

已经具备：

- `python-span-draft-v1`
- `java-collector-draft-v1`
- `java-http-trace-log-draft-v1`

其中最值得继续验证的是：

`java-http-trace-log-draft-v1`

因为它是按 Java `HttpDataPusher` 的 HTTP 上传方式对齐出来的。

## 6. 当前未完成的关键事项

### 6.1 数据面还没有被现网证明消费成功

虽然 Python 侧已经能本地产生 span、导出 payload、并尝试上传，但目前还没有被证明：

- 现网 log server / collector 会正确接受
- trace 数据会进入 AMDB / `tro_pradar`
- 控制台拓扑、压测明细、问题分析、容量水位会随之出数据

### 6.2 命令执行仍然不是主线

- `install/uninstall/upgrade` 还没有完整做成 Java 那种命令生命周期闭环
- 这不是当前第一阻塞点

### 6.3 插件生态远小于 Java

- Java 侧模块非常多
- Python 当前刻意先压缩范围，只优先保主链路

## 7. 关键困难与已发现的问题

### 7.1 Java 与 Python 的增强模型不同

Java 是：

- `ByteBuddy/Simulator`
- 插件输出统一 `SpanRecord`
- `Pradar` 再编码并推送 collector

Python 不是：

- 没有 JVM `-javaagent`
- 主要靠 monkey patch / wrapper
- patch 点常常是客户端 API 层，不是 Java 那种稳定的字节码增强点

因此不能简单按 Java 插件名一一硬搬。

### 7.2 控制面打通不等于控制台页面会出数据

已验证过的问题：

- 控制台能看到探针在线，不代表业务活动拓扑就会有数据
- 控制台问题分析、压测明细、容量水位没有数据，本质上不是心跳问题，而是数据面问题

也就是说：

`应用在线 ≠ trace/metrics 数据已被控制台消费`

### 7.3 Takin-web 依赖的不是“心跳数据”，而是 AMDB / tro_pradar / app_base_data

这点非常关键。

拓扑、问题分析、压测明细、容量水位这些模块依赖的是：

- AMDB 链路拓扑
- `tro_pradar` trace 数据
- `app_base_data` 机器/实例指标

所以后续如果控制台页面没数据，不要再只盯着注册/心跳接口，要直接去看 trace / metrics / collector 这条链路。

### 7.4 多个项目都和 agent 有关，但优先级不同

当前应当这样看：

- 第一优先级：`Takin-web`
  - 控制面主入口
  - 也是页面展示与数据消费的主要判断点
- 第二优先级：`takin-ee-web`
  - 对 trace / fast-debug / EE 扩展很关键
- 第三优先级：`agent-management`
  - 目前不是主阻塞点

## 8. 关键交互流程

### 8.1 控制面流程

目标：

`Python 应用启动 -> 探针注册 -> 定时心跳 -> 控制台下发配置 -> 探针应用配置`

Python 侧入口：

- `PyLinkAgent/pylinkagent/bootstrap.py`
- `PyLinkAgent/pylinkagent/controller/application_register.py`
- `PyLinkAgent/pylinkagent/controller/heartbeat.py`
- `PyLinkAgent/pylinkagent/controller/config_fetcher.py`
- `PyLinkAgent/pylinkagent/controller/external_api.py`

Java 参考位置：

- `D:\soft\agent\LinkAgent-main\simulator-agent\simulator-agent-core\src\main\java\com\shulie\instrument\simulator\agent\core\config\ExternalAPIImpl.java`
- `D:\soft\agent\LinkAgent-main\simulator-agent\simulator-agent-core\src\main\java\com\shulie\instrument\simulator\agent\core\scheduler\HttpAgentScheduler.java`
- `D:\soft\agent\LinkAgent-main\instrument-modules\user-modules\module-pradar-config-fetcher\src\main\java\com\shulie\instrument\module\config\fetcher\config\resolver\http\ApplicationConfigHttpResolver.java`

控制台 URL 常量位置：

- `D:\soft\agent\Takin-web\takin-web-common\src\main\java\io\shulie\takin\web\common\constant\AgentUrls.java`
- `D:\soft\agent\takin-ee-web\takin-web-ee-common\src\main\java\io\shulie\takin\common\EeAgentUrls.java`

已知核心 URL：

- `/api/agent/heartbeat`
- `/api/application/center/app/info`
- `/api/link/ds/configs/pull`
- `/api/remote/call/configs/pull`
- `/api/shadow/job/queryByAppName`
- `/api/global/switch/whitelist`
- `/api/application/center/app/switch/agent`

### 8.2 ZooKeeper 流程

目标：

`探针上线 -> 创建 EPHEMERAL 在线节点 -> 可选发现 log server -> 探针退出或 session timeout 后节点消失`

Python 侧入口：

- `PyLinkAgent/pylinkagent/controller/zk_integration.py`
- `PyLinkAgent/pylinkagent/zookeeper/zk_heartbeat.py`
- `PyLinkAgent/pylinkagent/zookeeper/zk_log_server.py`
- `PyLinkAgent/pylinkagent/zookeeper/config.py`

关键现实约束：

- 正常退出：节点应立即消失
- 强制 kill：只能等 ZK `session timeout`
- 这点要和 Java 对齐理解，不能误以为 Java 有额外的“强杀立删”逻辑

### 8.3 影子路由流程

目标：

`控制台下发影子库配置 -> Python 探针拉取并进入运行时 -> HTTP 入口识别压测流量 -> MySQL 切到影子库`

Python 侧入口：

- `PyLinkAgent/pylinkagent/controller/config_fetcher.py`
- `PyLinkAgent/pylinkagent/shadow/config_center.py`
- `PyLinkAgent/pylinkagent/http_server_interceptor.py`
- `PyLinkAgent/pylinkagent/shadow/mysql_interceptor.py`

当前本地最可靠的验证链路：

- `PyLinkAgent/examples/fastapi_mysql_shadow_demo/`

### 8.4 数据面 trace 流程

目标：

`入口请求 -> 本地 span 产生 -> exporter 编码 -> uploader 选择目标 -> 发送到 log server / collector -> 控制台数据消费`

Python 侧入口：

- `PyLinkAgent/pylinkagent/pradar/context.py`
- `PyLinkAgent/pylinkagent/pradar/pradar.py`
- `PyLinkAgent/pylinkagent/pradar/events.py`
- `PyLinkAgent/pylinkagent/pradar/exporter.py`
- `PyLinkAgent/pylinkagent/pradar/uploader.py`

Java 参考位置：

- `D:\soft\agent\LinkAgent-main\instrument-modules\user-modules\module-pradar-core\src\main\java\com\pamirs\pradar\interceptor\SpanRecord.java`
- `D:\soft\agent\LinkAgent-main\instrument-modules\user-modules\module-pradar-core\src\main\java\com\pamirs\pradar\TraceEncoder.java`
- `D:\soft\agent\LinkAgent-main\instrument-modules\user-modules\module-pradar-core\src\main\java\com\pamirs\pradar\Pradar.java`
- `D:\soft\agent\LinkAgent-main\instrument-modules\user-modules\module-log-data-pusher\src\main\java\com\shulie\instrument\module\log\data\pusher\push\http\HttpDataPusher.java`

当前推荐的协议模式：

- `PYLINKAGENT_SPAN_UPLOAD_PROTOCOL=java-http-trace-log-draft-v1`

## 9. 其他项目的关键代码位置

这一节只列后续最值得直接打开的代码位置。

### 9.1 Java Agent 主线

- `D:\soft\agent\LinkAgent-main\simulator-agent\simulator-agent-core\src\main\java\com\shulie\instrument\simulator\agent\core\config\ExternalAPIImpl.java`
  - Java agent 控制面 HTTP 交互基线
- `D:\soft\agent\LinkAgent-main\simulator-agent\simulator-agent-core\src\main\java\com\shulie\instrument\simulator\agent\core\scheduler\HttpAgentScheduler.java`
  - Java agent 命令调度基线
- `D:\soft\agent\LinkAgent-main\instrument-modules\user-modules\module-pradar-config-fetcher\src\main\java\com\shulie\instrument\module\config\fetcher\config\resolver\http\ApplicationConfigHttpResolver.java`
  - Java 配置抓取与事件传播入口
- `D:\soft\agent\LinkAgent-main\instrument-modules\user-modules\module-pradar-core\src\main\java\com\pamirs\pradar\interceptor\SpanRecord.java`
  - Java 插件统一 span 语义
- `D:\soft\agent\LinkAgent-main\instrument-modules\user-modules\module-pradar-core\src\main\java\com\pamirs\pradar\TraceEncoder.java`
  - Java trace 编码，内含 `TraceCollectorInvokeEncoder`
- `D:\soft\agent\LinkAgent-main\instrument-modules\user-modules\module-pradar-core\src\main\java\com\pamirs\pradar\Pradar.java`
  - Java trace/monitor/collector 核心入口
- `D:\soft\agent\LinkAgent-main\instrument-modules\user-modules\module-log-data-pusher\src\main\java\com\shulie\instrument\module\log\data\pusher\push\http\HttpDataPusher.java`
  - Java HTTP 数据推送方式，当前 Python draft uploader 的最直接参考

### 9.2 Takin-web

- `D:\soft\agent\Takin-web\takin-web-common\src\main\java\io\shulie\takin\web\common\constant\AgentUrls.java`
  - agent 相关核心 URL 常量
- `D:\soft\agent\Takin-web\takin-web-entrypoint\src\main\java\io\shulie\takin\web\entrypoint\controller\confcenter\ApplicationController.java`
  - 应用配置中心入口
- `D:\soft\agent\Takin-web\takin-web-amdb-accessor\src\main\java\io\shulie\takin\web\amdb\api\impl\ApplicationEntranceClientImpl.java`
  - 拓扑查询 AMDB 接口，含 `/amdb/link/getLinkTopology`
- `D:\soft\agent\Takin-web\takin-web-biz-service\src\main\java\io\shulie\takin\web\biz\service\LinkTopologyService.java`
  - 控制台拓扑组装逻辑
- `D:\soft\agent\Takin-web\takin-web-data\src\main\java\io\shulie\takin\web\data\dao\baseserver\BaseServerDaoImpl.java`
  - 直接体现 `tro_pradar` 与 `app_base_data` 的消费
- `D:\soft\agent\Takin-web\takin-web-biz-service\src\main\java\io\shulie\takin\web\biz\service\risk\impl\ProblemAnalysisServiceImpl.java`
  - 问题分析对基础指标数据的依赖
- `D:\soft\agent\Takin-web\takin-web-biz-service\src\main\java\io\shulie\takin\web\biz\service\report\impl\SummaryService.java`
  - 报表摘要与容量数据逻辑

### 9.3 takin-ee-web

- `D:\soft\agent\takin-ee-web\takin-web-ee-common\src\main\java\io\shulie\takin\common\EeAgentUrls.java`
  - EE 侧 agent URL 常量
- `D:\soft\agent\takin-ee-web\takin-web-ee-plugin\takin-web-ee-plugin-app-module\src\main\java\io\shulie\takin\web\plugin\app\service\trace\TraceLogServiceImpl.java`
  - trace log 查询服务
- `D:\soft\agent\takin-ee-web\takin-web-ee-plugin\takin-web-ee-plugin-app-module\src\main\java\io\shulie\takin\web\plugin\app\service\fastdebug\FastDebugServiceImpl.java`
  - fast-debug 与 trace 详情处理
- `D:\soft\agent\takin-ee-web\takin-web-ee-plugin\takin-web-ee-plugin-app-module\src\main\java\io\shulie\takin\web\plugin\app\controller\agent\AgentPushController.java`
  - agent push 相关入口

### 9.4 agent-management

- `D:\soft\agent\agent-management\agent-management\agent-management-client\src\main\java\io\shulie\agent\management\client\constant\AgentSpecification.java`
  - `trace-agent` / `sync-trace-agent` / `collector-agent` 定义
- `D:\soft\agent\agent-management\agent-management\agent-management-biz\src\main\java\io\shulie\agent\management\biz\constant\ServerConstant.java`
  - agent 管理相关常量

## 10. 建议下一个 AI 的阅读顺序

建议按下面顺序走，不要一上来就在所有仓库里乱跳。

1. 先读：
   - `PyLinkAgent/docs/project_background_and_handoff.md`
   - `PyLinkAgent/docs/architecture.md`
   - `PyLinkAgent/docs/trace_semantic_design.md`
   - `PyLinkAgent/docs/ai_handoff_intranet_validation.md`
2. 再读当前主线代码：
   - `pylinkagent/bootstrap.py`
   - `pylinkagent/controller/external_api.py`
   - `pylinkagent/controller/config_fetcher.py`
   - `pylinkagent/http_server_interceptor.py`
   - `pylinkagent/shadow/mysql_interceptor.py`
   - `pylinkagent/pradar/exporter.py`
   - `pylinkagent/pradar/uploader.py`
3. 再回看 Java 对照代码：
   - `ExternalAPIImpl.java`
   - `ApplicationConfigHttpResolver.java`
   - `SpanRecord.java`
   - `TraceEncoder.java`
   - `HttpDataPusher.java`
4. 最后再看控制台消费逻辑：
   - `AgentUrls.java`
   - `ApplicationEntranceClientImpl.java`
   - `LinkTopologyService.java`
   - `BaseServerDaoImpl.java`

## 11. 建议下一个 AI 的工作顺序

优先顺序建议如下：

1. 先确认控制面还是否稳定
   - 注册
   - 心跳
   - ZK 节点
   - 配置拉取
2. 再确认影子路由主链路
   - HTTP 入口识别
   - MySQL 影子库切换
3. 再推进数据面
   - span 是否产生
   - uploader 是否发送
   - 现网是否接收
4. 最后才扩插件面
   - Redis
   - Kafka
   - ES
   - 更多中间件

不要颠倒顺序。

## 12. 当前最值得继续做的事项

如果要继续推进，最值得做的是：

### 12.1 证明 trace 数据被现网消费

重点不是继续新增更多本地 span，而是证明：

- `java-http-trace-log-draft-v1` 是否被现网接收
- 接收后是否能落到控制台依赖的数据源
- 控制台是否开始出现拓扑 / 压测明细 / 问题分析 / 容量水位数据

### 12.2 如果现网不接受，优先修协议，不要先扩插件

如果当前 HTTP 上传协议仍不被现网接受：

- 继续对齐 `HttpDataPusher.java`
- 对齐 `TraceEncoder.java`
- 对齐响应格式、header、body 编码

不要在协议未通之前先扩大量中间件支持，否则返工概率很高。

## 13. 当前可用的验证入口

### 13.1 本地 demo

- `PyLinkAgent/examples/fastapi_mysql_shadow_demo/app.py`

### 13.2 运行时快照

- `GET /debug/runtime`

重点观察：

- `running`
- `agent_id`
- `zk_running`
- `selected_log_server`
- `recent_spans`
- `span_export_preview`
- `span_uploader`

### 13.3 诊断脚本

- `PyLinkAgent/scripts/diagnose.py`

## 14. 交接给下一个 AI 时最少要说明什么

如果要把当前代码交给另一个 Codex 或 AI，至少要同时给他：

1. 这份文档
2. `docs/ai_handoff_intranet_validation.md`
3. `docs/trace_semantic_design.md`
4. 当前内网联调结果

如果只给代码、不说明项目目标，后一个 AI 很容易误判为：

- 这是一个普通 Python APM
- 只要继续补插件数量就行
- 控制台没数据只是注册字段问题

这些判断都会把方向带偏。

