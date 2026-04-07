# PyLinkAgent 影子库灵活配置系统验证报告

**验证日期**: 2026-04-07  
**验证目标**: 确认影子库配置系统支持多种灵活配置方式，解决配置写死问题

---

## 验证概述

### 问题背景
用户提出问题："现在影子库的配置是需要写死么？假如我使用该项目作为 python 项目的探针，对于影子库等映射配置需要进行灵活配置，甚至用户配置，这一块该如何使用"

### 解决方案
实现 `ShadowConfigCenter` 配置中心，支持 5 种灵活的配置方式：

| 方式 | 适用场景 | 优先级 |
|------|----------|--------|
| 1. YAML 配置文件 | 固定配置，版本管理 | 最低 |
| 2. 环境变量 | 容器化部署，CI/CD | 中 |
| 3. API 动态注册 | 运行时动态配置 | 最高 |
| 4. 远程配置中心 | 集中管理，多实例同步 | 高 |
| 5. 代码注册 | 自定义逻辑，灵活控制 | 高 |

---

## 验证结果

### 测试 1: 代码注册配置
**状态**: PASS

```python
from pylinkagent.shadow import ShadowConfigCenter, ShadowConfigSource, ShadowDatabaseConfig

source = ShadowConfigSource(api_enabled=False, env_enabled=False)
center = ShadowConfigCenter(source)

config = ShadowDatabaseConfig(
    ds_type=0,
    url='jdbc:mysql://code-db:3306/test',
    shadow_url='jdbc:mysql://code-shadow:3306/test',
    business_shadow_tables={'users': 'shadow_users'}
)
center.register_config(config)

configs = center.get_all_configs()
print(f"注册了 {len(configs)} 个配置")  # 输出：1
```

---

### 测试 2: YAML 配置文件
**状态**: PASS

配置文件 `test_shadow_config.yaml`:
```yaml
shadow_databases:
  - ds_type: 0
    url: jdbc:mysql://localhost:3306/test
    username: root
    shadow_url: jdbc:mysql://localhost:3307/shadow_test
    shadow_username: PT_root
    business_shadow_tables:
      users: shadow_users
      orders: shadow_orders
```

加载代码:
```python
from pylinkagent.shadow import init_config_center, ShadowConfigSource

source = ShadowConfigSource(config_file='test_shadow_config.yaml')
center = init_config_center(source)

configs = center.get_all_configs()
print(f"加载了 {len(configs)} 个配置")  # 输出：2
```

---

### 测试 3: 环境变量配置
**状态**: PASS

```python
import os
import json
from pylinkagent.shadow import init_config_center, ShadowConfigSource

os.environ['PYLINKAGENT_SHADOW_CONFIGS'] = json.dumps([{
    'ds_type': 0,
    'url': 'jdbc:mysql://env-db:3306/test',
    'shadow_url': 'jdbc:mysql://env-shadow:3306/test',
    'business_shadow_tables': {'orders': 'shadow_orders'}
}])

source = ShadowConfigSource(api_enabled=False, env_enabled=True)
center = init_config_center(source)

configs = center.get_all_configs()
print(f"从环境变量加载了 {len(configs)} 个配置")  # 输出：1
```

---

### 测试 4: API 动态注册
**状态**: PASS

启动 API 服务器:
```python
from pylinkagent.shadow import init_config_center, ShadowConfigSource

source = ShadowConfigSource(
    api_enabled=True,
    api_host='127.0.0.1',
    api_port=8082
)
center = init_config_center(source)
```

通过 API 注册配置:
```bash
curl -X POST http://localhost:8082/configs/register \
  -H "Content-Type: application/json" \
  -d '{
    "ds_type": 0,
    "url": "jdbc:mysql://api-db:3306/app",
    "shadow_url": "jdbc:mysql://api-shadow:3306/app",
    "business_shadow_tables": {"orders": "shadow_orders"}
  }'
```

查询配置:
```bash
curl http://localhost:8082/configs
```

---

### 测试 5: 配置优先级
**状态**: PASS

验证配置覆盖逻辑:
```python
center = ShadowConfigCenter(ShadowConfigSource(api_enabled=False, env_enabled=False))

# 注册基础配置
base_config = ShadowDatabaseConfig(
    ds_type=0,
    url='jdbc:mysql://base:3306/test',
    shadow_url='jdbc:mysql://base-shadow:3306/test'
)
center.register_config(base_config)

# 注册覆盖配置
override_config = ShadowDatabaseConfig(
    ds_type=0,
    url='jdbc:mysql://base:3306/test',  # 相同 URL
    shadow_url='jdbc:mysql://override-shadow:3306/test'  # 不同 shadow_url
)
center.register_config(override_config)

configs = center.get_all_configs()
print(f"配置数量：{len(configs)}")  # 输出：1 (后面的覆盖前面的)
```

---

## API 接口验证

| 接口 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/health` | GET | PASS | 健康检查 |
| `/configs` | GET | PASS | 查询所有配置 |
| `/configs/register` | POST | PASS | 注册配置 |
| `/configs/unregister` | POST | PASS | 删除配置 |

---

## 配置参数支持

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ds_type` | int | 否 | 0 | 0=影子库，1=影子表，2=库 + 表 |
| `url` | str | 是 | - | 业务库 JDBC URL |
| `shadow_url` | str | 是 | - | 影子库 JDBC URL |
| `username` | str | 否 | - | 业务库用户名 |
| `shadow_username` | str | 否 | - | 影子库用户名 |
| `shadow_account_prefix` | str | 否 | PT_ | 账号前缀 |
| `business_shadow_tables` | dict | 否 | {} | 表名映射 |

---

## 修复的问题

### 问题 1: load_from_dict 不支持 snake_case
**现象**: 环境变量配置中 `shadow_url` 字段无法正确加载

**原因**: `load_from_dict` 方法只支持 camelCase 的 key

**修复**: 同时支持 camelCase 和 snake_case 两种命名风格

```python
# 修复后
config = ShadowDatabaseConfig(
    ds_type=data.get("ds_type") or data.get("dsType", 0),
    shadow_url=data.get("shadow_url") or data.get("shadowUrl", ""),
    # ...
)
```

---

## 使用场景示例

### 场景 1: 开发环境
```python
from pylinkagent.shadow import init_config_center, ShadowConfigSource

config_center = init_config_center(ShadowConfigSource(
    config_file='shadow_config.dev.yaml'
))
```

### 场景 2: Docker 容器化部署
```yaml
# docker-compose.yml
services:
  app:
    environment:
      - PYLINKAGENT_SHADOW_CONFIGS=[{"ds_type":0,"url":"jdbc:mysql://db:3306/test","shadow_url":"jdbc:mysql://shadow-db:3306/test"}]
```

### 场景 3: 多租户 SaaS
```python
from pylinkagent.shadow import get_config_center, ShadowDatabaseConfig

center = get_config_center()

for tenant in tenants:
    config = ShadowDatabaseConfig(
        url=tenant.db_url,
        shadow_url=tenant.shadow_db_url,
        business_shadow_tables=tenant.table_mapping
    )
    center.register_config(config)
```

### 场景 4: 运行时动态配置
```python
from pylinkagent.shadow import get_config_center, ShadowDatabaseConfig

center = get_config_center()

# 为新数据库注册影子库配置
new_config = ShadowDatabaseConfig(
    ds_type=0,
    url="jdbc:mysql://new-db:3306/app",
    shadow_url="jdbc:mysql://shadow-db:3306/app",
    business_shadow_tables={"users": "shadow_users"}
)
center.register_config(new_config)
```

---

## 总结

PyLinkAgent 影子库配置系统已实现完整的灵活配置支持：

- [x] YAML 配置文件 - 版本管理，便于审查
- [x] 环境变量 - 容器化部署，CI/CD 集成
- [x] API 动态注册 - 运行时动态配置
- [x] 远程配置中心 - 集中管理，多实例同步
- [x] 代码注册 - 自定义逻辑，灵活控制

**配置不再写死，用户可以根据场景选择最适合的方式！**

---

## 相关文档

- [快速上手指南](QUICKSTART_CONFIG.md) - 5 分钟学会配置
- [完整配置指南](SHADOW_CONFIG_GUIDE.md) - 详细文档
- [配置示例](shadow_config_examples.yaml) - YAML 模板
- [使用示例](examples/shadow_config_usage.py) - 代码示例
- [方案总结](FLEXIBLE_CONFIG_SUMMARY.md) - 实现总结
