# PyLinkAgent 影子路由指南

> **版本**: v2.1.0
> **更新日期**: 2026-04-23
> **主题**: 影子数据库/服务器自动路由

---

## 一、概述

影子路由是 PyLinkAgent 的核心功能，在压测流量下自动将请求路由到影子数据库/服务器。

### 1.1 支持的组件

| 组件 | 拦截目标 | 路由方式 | 文件 |
|------|---------|---------|------|
| **MySQL** | `pymysql.connect()` | 替换连接参数 | `pylinkagent/shadow/mysql_interceptor.py` |
| **SQLAlchemy** | `create_engine()` | 重写 URL / SQL 注入 | `pylinkagent/shadow/sqlalchemy_interceptor.py` |
| **Redis** | `redis.Redis()` | 替换 host/port/db | `pylinkagent/shadow/redis_interceptor.py` |
| **Elasticsearch** | `Elasticsearch()` | 替换 hosts | `pylinkagent/shadow/es_interceptor.py` |
| **Kafka** | `KafkaProducer/Consumer` | 替换 servers + topic 映射 | `pylinkagent/shadow/kafka_interceptor.py` |
| **HTTP** | `requests` / `httpx` | 注入压测标头 | `pylinkagent/shadow/http_interceptor.py` |

### 1.2 影子库模式

| 模式 | dsType | 说明 |
|------|--------|------|
| **独立影子库** | 0 | 完全独立的影子数据库 (shadowDbConfig.dataSources[1]) |
| **同库影子表** | 1 | 同一库内，使用 PT_ 前缀的影子表 (shadowTableConfig) |
| **库+表混合** | 2 | 影子库 + 影子表 |

---

## 二、配置来源

### 2.1 API 端点

| 组件 | HTTP 端点 | 方法 |
|------|-----------|------|
| MySQL / 数据库 | `GET /api/link/ds/configs/pull?appName=xxx` | 影子库配置 |
| Redis | `GET /api/link/ds/server/configs/pull?appName=xxx` | 影子 Redis |
| Elasticsearch | `GET /api/link/es/server/configs/pull?appName=xxx` | 影子 ES |
| Kafka / MQ | `GET /api/agent/configs/shadow/consumer?appName=xxx` | 影子 Kafka |
| 定时任务 | `GET /api/shadow/job/queryByAppName?appName=xxx` | 影子 Job |

### 2.2 真实 API 响应格式

**dsType=0 (独立影子库)**:
```json
{
  "success": true,
  "data": [{
    "applicationName": "my-app",
    "dsType": 0,
    "url": "jdbc:mysql://7.198.147.127:3306/wefire_db_sit",
    "shadowTableConfig": null,
    "shadowDbConfig": {
      "datasourceMediator": {
        "dataSourceBusiness": "dataSourceBusiness",
        "dataSourcePerformanceTest": "dataSourcePerformanceTest"
      },
      "dataSources": [
        {
          "id": "dataSourceBusiness",
          "url": "jdbc:mysql://7.198.147.127:3306/wefire_db_sit",
          "username": "wefireSitAdmin",
          "password": null
        },
        {
          "id": "dataSourcePerformanceTest",
          "url": "jdbc:mysql://7.198.147.127:3306/pt_wefire_db_sit",
          "username": "drpAdmin",
          "password": "Flzx3qc###"
        }
      ]
    }
  }]
}
```

**dsType=1 (同库影子表)**:
```json
{
  "success": true,
  "data": [{
    "dsType": 1,
    "url": "jdbc:mysql://localhost:3306/app",
    "shadowTableConfig": "users,orders,products",
    "shadowDbConfig": null
  }]
}
```

---

## 三、完整数据流

```
┌─ 配置拉取 (每 60 秒) ──────────────────────────────────┐
│                                                         │
│  ConfigFetcher._fetch_loop()                            │
│    → fetch_now()                                        │
│      → external_api.fetch_shadow_database_config()      │
│        GET /api/link/ds/configs/pull?appName=xxx        │
│        返回 JSON (见 2.2)                                │
│                                                         │
│      → ShadowDatabaseConfig.from_dict(item)             │
│        dsType=0: 从 shadowDbConfig.dataSources[]       │
│                   按 ID 匹配业务库/影子库                │
│        dsType=1: 从 shadowTableConfig 解析逗号分隔表名   │
│                                                         │
│      → ConfigData.shadow_database_configs               │
│        key = _normalize_url(url)                        │
│        value = ShadowDatabaseConfig                      │
│                                                         │
├─ 配置变更通知 ──────────────────────────────────────────┤
│                                                         │
│      → _check_config_games() 对比新旧配置               │
│      → _notify_config_change() 触发回调                  │
│                                                         │
├─ 更新 ShadowConfigCenter ───────────────────────────────┤
│                                                         │
│  bootstrap._on_shadow_config_change(config_center)      │
│    → config = _config_fetcher.get_config()              │
│    → config_center.load_db_configs(配置列表)            │
│      → _db_configs = {normalized_url: config}            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 配置解析步骤 (dsType=0)

```python
from pylinkagent.shadow.config_center import ShadowDatabaseConfig

api_item = { ... }  # API 返回的单条记录
config = ShadowDatabaseConfig.from_dict(api_item)

# 解析结果:
# config.url          = "jdbc:mysql://7.198.147.127:3306/wefire_db_sit"
# config.username     = "wefireSitAdmin"
# config.shadow_url   = "jdbc:mysql://7.198.147.127:3306/pt_wefire_db_sit"
# config.shadow_username = "drpAdmin"
# config.shadow_password = "Flzx3qc###"
# config.ds_type      = 0
```

---

## 四、路由流程

### 4.1 启动阶段

```
bootstrap._init_shadow_routing()
  1. get_config_center() → 全局单例
  2. get_router()        → 全局单例
  3. ConfigFetcher.on_config_change() → 注册回调
  4. 创建 5 个拦截器，调用 patch() 注入:
     pymysql.connect()     → MySQLShadowInterceptor
     redis.Redis()         → RedisShadowInterceptor
     Elasticsearch()       → ESShadowInterceptor
     KafkaProducer/Consumer → KafkaShadowInterceptor
     requests/httpx        → HTTPShadowInterceptor
```

### 4.2 运行时拦截

```
应用代码: conn = pymysql.connect(host='localhost', port=3306, db='test')
    ↓
pymysql.connect 已被 _wrapped_connect() 替换
    ↓
MySQLShadowInterceptor._wrapped_connect()
  1. 提取连接参数: host, port, database
  2. 构建 original_url = "jdbc:mysql://localhost:3306/test"
  3. router.route_mysql(original_url, user, password)
       ↓
ShadowRouter.route_mysql(original_url, ...)
  Gate 1: PradarSwitcher.is_cluster_test_enabled() — 全局压测开关
  Gate 2: Pradar.is_cluster_test() — 当前请求是否染色为压测流量
       ↓ (两门都为 True)
  config_center.get_db_config(original_url)
    → _normalize_url(url) → 去掉 "jdbc:" 前缀, 转小写
    → _db_configs.get(key) → ShadowDatabaseConfig
       ↓
  根据 dsType 决策:
    dsType=0 → _parse_mysql_url(shadow_url, ...)
      → {"host": ..., "port": 3307, "database": "pt_xxx",
         "user": "drpAdmin", "password": "xxx"}
    dsType=1 → {"mode": "same_db"} — 连接不变，SQL 层面重写表名
    dsType=2 → 同 dsType=0 + SQL 重写
       ↓
回到 wrapper，替换 kwargs:
  kwargs['host']     = shadow_params['host']
  kwargs['port']     = 3307
  kwargs['database'] = 'pt_wefire_db_sit'
  kwargs['user']     = 'drpAdmin'
  kwargs['password'] = 'Flzx3qc###'
    ↓
调用原始 pymysql.connect(...) → 返回影子库连接
```

---

## 五、SQL 重写 (dsType=1/2)

### 5.1 自动 PT_ 前缀

```python
from pylinkagent.shadow.sql_rewriter import AutoPrefixRewriter

rewriter = AutoPrefixRewriter('PT_')
sql = 'SELECT * FROM users JOIN orders ON users.id = orders.user_id'
rewritten = rewriter.rewrite(sql)
# → 'SELECT * FROM PT_users JOIN PT_orders ON ...'
```

### 5.2 映射表重写

```python
from pylinkagent.shadow.sql_rewriter import ShadowSQLRewriter

rewriter = ShadowSQLRewriter({
    'users': 'shadow_users',
    'orders': 'shadow_orders',
})
sql = 'SELECT * FROM users WHERE id = 1'
rewritten = rewriter.rewrite(sql)
# → 'SELECT * FROM shadow_users WHERE id = 1'
```

---

## 六、验证方法

### 6.1 运行影子路由验证

```bash
cd PyLinkAgent
python scripts/verify_shadow_routing.py
```

预期输出: **37/37 通过** (含 9 个真实 API 格式解析测试)

### 6.2 运行综合验证

```bash
# 设置环境变量
export MANAGEMENT_URL=http://<控制台IP>:9999
export APP_NAME=your-app
export SIMULATOR_ZK_SERVERS=<ZK地址>

python scripts/comprehensive_verification.py
```

### 6.3 验证项目

| 测试 | 内容 |
|------|------|
| 配置中心 | 注册/查找/批量加载 |
| 真实 API 解析 | dsType=0/1 格式、shadowDbConfig.dataSources 解析 |
| 路由器 | 路由决策/影子表名映射 |
| SQL 重写 | SELECT/INSERT/JOIN/自动前缀 |
| 路由上下文 | ThreadLocal 状态管理 |
| Pradar 前缀 | PT_ 前缀工具 |
| 拦截器 | 所有组件拦截器创建 |
| 全局单例 | 配置中心和路由器 |

---

## 七、故障排查

### 问题 1: 影子路由未生效

**检查**:
1. `SHADOW_ROUTING` 环境变量是否为 `true`
2. `PradarSwitcher.is_cluster_test_enabled()` 是否为 `True`
3. 当前请求是否设置了 `cluster_test=True`

### 问题 2: MySQL 路由失败

**检查**:
1. ConfigFetcher 是否正常拉取 (日志: `配置拉取成功`)
2. `shadowDbConfig.dataSources` 是否包含业务库和影子库两条记录
3. 影子服务器是否可达

### 问题 3: 配置解析后 shadow_url 为空

**原因**: API 返回格式不匹配。真实 API 的 shadow_url 在 `shadowDbConfig.dataSources[1].url` 中，不是顶层 `shadowUrl` 字段。

**确认**: 检查 `config_fetcher.py` 和 `shadow/config_center.py` 的版本是否匹配真实 API。

### 问题 4: SQL 重写不生效

**检查**:
1. 表名是否在 `shadowTableConfig` 中
2. SQL 语句格式是否正确 (FROM/JOIN/UPDATE 后跟表名)
3. 是否使用 ds_type 1 或 2

---

**文档完成日期**: 2026-04-23
**版本**: v2.1
