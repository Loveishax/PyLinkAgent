# PyLinkAgent 影子路由指南

> **版本**: v2.0.0
> **更新日期**: 2026-04-23
> **主题**: 影子数据库/服务器自动路由

---

## 一、概述

影子路由是 PyLinkAgent 的核心功能，在压测流量下自动将请求路由到影子数据库/服务器。

### 1.1 支持的组件

| 组件 | 拦截目标 | 路由方式 | 文件 |
|------|---------|---------|------|
| **MySQL** | `pymysql.connect()` | 替换连接参数 | `shadow/mysql_interceptor.py` |
| **SQLAlchemy** | `create_engine()` | 重写 URL / SQL 注入 | `shadow/sqlalchemy_interceptor.py` |
| **Redis** | `redis.Redis()` | 替换 host/port/db | `shadow/redis_interceptor.py` |
| **Elasticsearch** | `Elasticsearch()` | 替换 hosts | `shadow/es_interceptor.py` |
| **Kafka** | `KafkaProducer/Consumer` | 替换 servers + topic 映射 | `shadow/kafka_interceptor.py` |
| **HTTP** | `requests` / `httpx` | 注入压测标头 | `shadow/http_interceptor.py` |

### 1.2 影子库模式

| 模式 | ds_type | 说明 |
|------|---------|------|
| **独立影子库** | 0 | 完全独立的影子数据库 (shadow_url) |
| **同库影子表** | 1 | 同一库内，使用 PT_ 前缀的影子表 |
| **库+表混合** | 2 | 影子库 + 影子表 |

---

## 二、核心架构

```
控制台 (Takin-web)
  | GET /api/link/ds/configs/pull?appName=xxx
  v
ExternalAPI → ConfigFetcher (60s 定时拉取)
  | 解析为 ShadowDatabaseConfig
  v
ShadowConfigCenter (配置存储 + 热更新)
  | 通知 ShadowRouter
  v
ShadowRouter (路由决策)
  | 检查: PradarSwitcher + Pradar.is_cluster_test()
  | 匹配: ShadowDatabaseConfig
  v
Shadow 拦截器 (wrapt)
  | pymysql.connect() → 影子连接
  | redis.Redis() → 影子 Redis
  | Elasticsearch() → 影子 ES
  | Kafka Producer/Consumer → 影子 Kafka
  v
影子服务器
```

### 2.1 两门路由判断

```python
def should_route() -> bool:
    # Gate 1: 全局开关 (控制台控制)
    if not PradarSwitcher.is_cluster_test_enabled():
        return False
    # Gate 2: 流量染色 (HTTP 标头/消息标头)
    return Pradar.is_cluster_test()
```

---

## 三、配置说明

### 3.1 环境变量

```bash
# 启用影子路由 (默认 true)
export SHADOW_ROUTING=true

# 压测流量开关 (通过控制台命令控制)
# PradarSwitcher 压测开关
```

### 3.2 配置格式 (API 返回)

```json
{
  "dataSourceName": "master",
  "url": "jdbc:mysql://localhost:3306/test",
  "username": "root",
  "shadowUrl": "jdbc:mysql://localhost:3307/shadow_test",
  "shadowUsername": "PT_root",
  "dsType": 0,
  "businessShadowTables": {
    "users": "shadow_users",
    "orders": "shadow_orders"
  }
}
```

---

## 四、SQL 重写

### 4.1 映射表重写

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

### 4.2 自动前缀重写

```python
from pylinkagent.shadow.sql_rewriter import AutoPrefixRewriter

rewriter = AutoPrefixRewriter('PT_')
sql = 'SELECT * FROM users JOIN orders ON users.id = orders.user_id'
rewritten = rewriter.rewrite(sql)
# → 'SELECT * FROM PT_users JOIN PT_orders ON ...'
```

---

## 五、验证方法

### 5.1 运行影子路由验证

```bash
cd PyLinkAgent
python scripts/verify_shadow_routing.py
```

预期输出: 28/28 通过

### 5.2 验证项目

- 配置中心: 注册/查找/批量加载
- 路由器: 路由决策/影子表名映射
- SQL 重写: SELECT/INSERT/JOIN/自动前缀
- 路由上下文: ThreadLocal 状态管理
- Pradar 前缀: PT_ 前缀工具
- 拦截器: 所有组件拦截器创建
- 全局单例: 配置中心和路由器

---

## 六、故障排查

### 问题 1: 影子路由未生效

**检查**:
1. `SHADOW_ROUTING` 环境变量是否为 `true`
2. `PradarSwitcher.is_cluster_test_enabled()` 是否为 `True`
3. 当前请求是否设置了 `cluster_test=True`

### 问题 2: MySQL 路由失败

**检查**:
1. 影子库配置是否正确注册
2. 原始 URL 是否匹配
3. 影子服务器是否可达

### 问题 3: SQL 重写不生效

**检查**:
1. 表名是否在 `business_shadow_tables` 映射中
2. SQL 语句格式是否正确
3. 是否使用 ds_type 1 或 2

---

**文档完成日期**: 2026-04-23
**版本**: v1.0
