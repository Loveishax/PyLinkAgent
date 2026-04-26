# PyLinkAgent 影子路由现状

影子路由是当前阶段最重要的业务功能，但这份文档只描述当前代码已经具备的能力和仍然存在的缺口。

## 1. 当前已接入的拦截器

- `pylinkagent/shadow/mysql_interceptor.py`
- `pylinkagent/shadow/sqlalchemy_interceptor.py`
- `pylinkagent/shadow/redis_interceptor.py`
- `pylinkagent/shadow/es_interceptor.py`
- `pylinkagent/shadow/kafka_interceptor.py`
- `pylinkagent/shadow/http_interceptor.py`

`bootstrap._init_shadow_routing()` 当前会尝试 patch 上述 interceptor。

## 2. 当前依赖的核心组件

- `ShadowConfigCenter`: 保存影子库、Redis、ES、Kafka 配置
- `ShadowRouter`: 根据当前上下文决定是否切换到影子目标
- `Pradar` / `PradarSwitcher`: 压测标记与全局开关
- `ConfigFetcher`: 从控制台拉配置并触发回调

## 3. 当前已经收敛的部分

- `bootstrap` 会在启动 `ConfigFetcher` 后再初始化影子路由
- 影子配置变更回调已能在启动后触发
- `SQLAlchemy` interceptor 已被纳入默认 patch 列表
- 关闭时会针对真实 interceptor 实例执行 `unpatch()`

## 4. 当前仍然存在的关键缺口

### 配置消费不完整

虽然 `ExternalAPI` 已定义了多类配置拉取接口，但当前真正接进主链路并自动灌入运行时的仍然主要是影子库配置。

### 压测染色链路仍待加强

目前代码中已有 `pradar` 基础类和 `HTTP` 拦截器，但“入口染色 -> 上下文传递 -> 下游路由”的闭环仍需继续按 Java Agent 对齐。

### 端到端隔离仍待验收

当前不能把“存在 MySQL/Redis/ES/Kafka interceptor”直接等同于“已经实现 Java Agent 级别的数据隔离”。

## 5. 当前建议的验收顺序

1. 控制台能下发影子库配置
2. `ConfigFetcher` 能拉到影子库配置
3. `ShadowConfigCenter` 能收到并保存配置
4. 压测标记请求进入后，MySQL 连接参数切换到影子库
5. 非压测请求保持业务库不变

MySQL 是第一优先级。Redis、Kafka、ES 建议在 MySQL 闭环后再逐项验收。
