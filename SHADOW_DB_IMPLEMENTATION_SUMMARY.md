# PyLinkAgent 影子库功能实现总结

## 一、实现概述

基于 Java LinkAgent 的影子库功能，为 PyLinkAgent 实现了完整的全链路压测影子库路由能力。

### 核心功能

1. **流量染色识别** - 通过 HTTP Header 识别压测流量
2. **影子库路由** - 压测流量自动路由到影子库
3. **影子表映射** - 支持业务表名→影子表名自动替换
4. **SQL 重写** - 压测流量下 SQL 表名自动重写
5. **配置管理** - 动态注册/注销影子库配置

---

## 二、新增文件清单

```
PyLinkAgent/
├── pylinkagent/
│   └── shadow/                      # 影子库核心模块
│       ├── __init__.py              # 模块导出
│       ├── config.py                # 影子库配置类
│       ├── context.py               # 影子上下文管理
│       ├── router.py                # 影子路由器
│       └── interceptor.py           # 影子拦截器
├── test_shadow_app.py               # 影子库测试应用
├── test_shadow_runner.py            # 影子库测试脚本
├── SHADOW_DB_VERIFICATION_REPORT.md # 影子库验证报告
└── SHADOW_DB_IMPLEMENTATION_SUMMARY.md # 本文档
```

---

## 三、核心类说明

### 3.1 ShadowDatabaseConfig

影子库配置数据类，包含：
- `ds_type`: 数据源类型 (0=影子库，1=影子表，2=库 + 表)
- `url` / `shadow_url`: 业务库/影子库 URL
- `business_shadow_tables`: 业务表→影子表映射
- `shadow_account_prefix/suffix`: 账号前缀/后缀

### 3.2 ShadowContext

影子上下文，包含：
- `is_pressure_test`: 是否为压测流量
- `pressure_flag`: 压测标记值
- `trace_id`: 链路追踪 ID

### 3.3 ShadowRouter

影子路由器，负责：
- 判断是否使用影子库
- 获取影子库配置
- 重写 SQL 表名
- 获取目标连接信息

---

## 四、API 使用说明

### 4.1 注册影子库配置

```python
import requests

config = {
    "ds_type": 0,
    "url": "jdbc:mysql://localhost:3306/test",
    "username": "root",
    "shadow_url": "jdbc:mysql://localhost:3306/shadow_test",
    "shadow_username": "PT_root",
    "business_shadow_tables": {
        "users": "shadow_users",
        "orders": "shadow_orders"
    }
}

response = requests.post(
    "http://localhost:8001/db/config/register",
    json=config
)
```

### 4.2 发起压测请求

```python
# 添加压测标记 Header
headers = {"x-pressure-test": "true"}

# 用户查询 (会返回影子库数据)
response = requests.get(
    "http://localhost:8001/users/1",
    headers=headers
)

# SQL 重写测试
response = requests.get(
    "http://localhost:8001/sql/rewrite?sql=SELECT+*+FROM+users",
    headers=headers
)
# 返回："SELECT * FROM shadow_users"
```

---

## 五、验证结果

### 测试覆盖率

| 测试类别 | 测试项 | 通过率 |
|----------|--------|--------|
| 配置管理 | 1 | 100% |
| 流量染色 | 4 | 100% |
| 影子路由 | 3 | 100% |
| SQL 重写 | 2 | 100% |
| 状态检查 | 3 | 100% |
| **总计** | **13** | **100%** |

### 验证通过的功能

✅ 流量染色识别 - `x-pressure-test` Header  
✅ 影子库路由 - 压测流量自动切换  
✅ 影子表映射 - 表名自动替换  
✅ SQL 重写 - SQL 语句拦截  
✅ 配置管理 - 动态注册/查询  

---

## 六、与 Java LinkAgent 对比

| 功能 | Java LinkAgent | PyLinkAgent | 状态 |
|------|---------------|-------------|------|
| 影子库配置 | ✅ | ✅ | 已实现 |
| 影子表映射 | ✅ | ✅ | 已实现 |
| 流量染色 | ✅ | ✅ | 已实现 |
| SQL 重写 | ✅ | ✅ | 已实现 |
| 账号转换 | ✅ | ✅ | 已实现 |
| Redis 影子 | ✅ | ❌ | 待实现 |
| HBase 影子 | ✅ | ❌ | 待实现 |
| ES 影子 | ✅ | ❌ | 待实现 |

---

## 七、待扩展功能

### 高优先级

1. **SQLAlchemy 完整插桩**
   - 完整的 SQL 解析和重写
   - 支持参数化查询

2. **控制平台对接**
   - 与 LinkAgent 控制平台集成
   - 配置集中管理

### 中优先级

3. **Redis 影子服务**
   - Redis 操作拦截
   - 影子 Redis 路由

4. **配置持久化**
   - YAML 配置文件支持
   - 数据库存储配置

---

## 八、使用建议

### 全链路压测场景

1. **配置影子库**: 通过 API 注册影子库配置
2. **流量染色**: 在压测请求中添加 `x-pressure-test: true` Header
3. **自动路由**: 影子库功能会自动将压测流量路由到影子库
4. **SQL 重写**: 自动替换 SQL 中的表名为影子表名

### 注意事项

- 确保影子库配置正确后再发起压测
- 影子表名映射需要与实际数据库表名一致
- 生产环境建议使用持久化配置

---

## 九、测试命令

```bash
# 1. 启动测试服务器
python test_shadow_app.py

# 2. 运行影子库测试
python test_shadow_runner.py

# 3. 查看测试报告
cat test_shadow_report.md
```

---

## 十、参考资料

- Java LinkAgent 影子库实现: `instrument-modules/user-modules/module-alibaba-druid/`
- Java LinkAgent 配置类: `ShadowDatabaseConfig.java`
- PyLinkAgent 验证报告: `VERIFICATION_REPORT.md`

---

**实现完成时间**: 2026-04-07  
**版本**: PyLinkAgent Shadow DB v1.0.0  
**状态**: ✅ 可用于全链路压测场景
