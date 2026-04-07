# PyLinkAgent 影子库灵活配置方案

> **解决影子库配置写死问题，支持多种灵活配置方式**

---

## 🎯 问题背景

之前 PyLinkAgent 的影子库配置是"写死"在代码中的，存在以下问题：

1. ❌ 配置硬编码，修改需要改代码
2. ❌ 不同环境需要不同配置，难以管理
3. ❌ 用户无法自定义配置
4. ❌ 无法动态更新配置

---

## ✅ 解决方案

现在 PyLinkAgent 支持 **5 种灵活的配置方式**：

| 方式 | 适用场景 | 示例 |
|------|----------|------|
| **YAML 配置文件** | 固定配置，版本管理 | `shadow_config.yaml` |
| **环境变量** | 容器化部署，CI/CD | `PYLINKAGENT_SHADOW_*` |
| **API 动态注册** | 运行时动态配置 | `POST /configs/register` |
| **远程配置中心** | 集中管理，多实例 | 控制台下发 |
| **代码注册** | 自定义逻辑 | `register_config()` |

---

## 📖 使用指南

### 方式 1: YAML 配置文件

创建 `shadow_config.yaml`：

```yaml
shadow_databases:
  - ds_type: 0
    url: jdbc:mysql://localhost:3306/test
    username: root
    shadow_url: jdbc:mysql://localhost:3307/shadow_test
    shadow_username: PT_root
    shadow_account_prefix: PT_
    business_shadow_tables:
      users: shadow_users
      orders: shadow_orders
```

加载配置：

```python
from pylinkagent.shadow import init_config_center, ShadowConfigSource

source = ShadowConfigSource(config_file="shadow_config.yaml")
config_center = init_config_center(source)
```

---

### 方式 2: 环境变量

适合 Docker 容器化部署：

```bash
export PYLINKAGENT_SHADOW_CONFIGS='[{
  "ds_type": 0,
  "url": "jdbc:mysql://db:3306/test",
  "shadow_url": "jdbc:mysql://shadow-db:3306/test",
  "business_shadow_tables": {"users": "shadow_users"}
}]'

python app.py
```

---

### 方式 3: API 动态注册

启动 API 服务器：

```python
from pylinkagent.shadow import init_config_center, ShadowConfigSource

source = ShadowConfigSource(
    api_enabled=True,
    api_host="0.0.0.0",
    api_port=8081
)
config_center = init_config_center(source)
```

注册配置：

```bash
curl -X POST http://localhost:8081/configs/register \
  -H "Content-Type: application/json" \
  -d '{
    "ds_type": 0,
    "url": "jdbc:mysql://localhost:3306/test",
    "shadow_url": "jdbc:mysql://localhost:3307/shadow_test",
    "business_shadow_tables": {"users": "shadow_users"}
  }'
```

---

### 方式 4: 远程配置中心

与 LinkAgent 控制平台集成：

```python
from pylinkagent.shadow import init_config_center, ShadowConfigSource

source = ShadowConfigSource(
    remote_enabled=True,
    remote_url="http://control-center:8080/api/shadow-configs",
    remote_api_key="your-api-key",
    remote_poll_interval=60
)
config_center = init_config_center(source)
```

---

### 方式 5: 代码注册

适合动态场景：

```python
from pylinkagent.shadow import (
    ShadowDatabaseConfig,
    get_config_center
)

center = get_config_center()

config = ShadowDatabaseConfig(
    ds_type=0,
    url="jdbc:mysql://db:3306/app",
    shadow_url="jdbc:mysql://shadow-db:3306/app",
    business_shadow_tables={"users": "shadow_users"}
)

center.register_config(config)
```

---

## 🔄 配置优先级

```
┌─────────────────────────────────┐
│  1. YAML 配置文件 (最低优先级)    │
│     ↓                           │
│  2. 环境变量 (覆盖文件配置)       │
│     ↓                           │
│  3. 远程配置中心 (覆盖环境变量)   │
│     ↓                           │
│  4. API 动态注册 (最高优先级)     │
└─────────────────────────────────┘
```

---

## 📁 新增文件

```
PyLinkAgent/
├── pylinkagent/
│   └── shadow/
│       └── config_center.py      # 配置中心核心代码
├── examples/
│   └── shadow_config_usage.py    # 使用示例
├── SHADOW_CONFIG_GUIDE.md        # 配置指南
└── shadow_config_examples.yaml   # 配置示例
```

---

## 🎯 典型场景

### 场景 1: 开发环境

```python
# 使用本地 YAML 配置文件
from pylinkagent.shadow import init_config_center

config_center = init_config_center()
config_center._load_from_file("shadow_config.dev.yaml")
```

### 场景 2: 生产环境

```yaml
# docker-compose.yml
services:
  app:
    environment:
      - PYLINKAGENT_SHADOW_CONFIG_FILE=/etc/pylinkagent/shadow.yaml
      - PYLINKAGENT_SHADOW_ACCOUNT_PREFIX=PT_
    volumes:
      - ./shadow_config.prod.yaml:/etc/pylinkagent/shadow.yaml
```

### 场景 3: 多租户

```python
# 为每个租户动态注册配置
for tenant in tenants:
    config = ShadowDatabaseConfig(
        url=tenant.db_url,
        shadow_url=tenant.shadow_db_url,
        business_shadow_tables=tenant.table_mapping
    )
    register_config(config)
```

### 场景 4: SaaS 平台

```python
# 用户通过控制台配置影子库
@app.post("/api/user/shadow-config")
def create_shadow_config(user_id: str, config_data: dict):
    config = ShadowDatabaseConfig(**config_data)
    get_config_center().register_config(config)
    return {"status": "success"}
```

---

## 🔧 API 接口

配置中心提供 REST API：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/configs` | GET | 查询所有配置 |
| `/configs/register` | POST | 注册配置 |
| `/configs/unregister` | POST | 删除配置 |

---

## 📊 配置参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ds_type` | int | 否 | 0 | 0=影子库，1=影子表，2=库 + 表 |
| `url` | str | 是 | - | 业务库 URL |
| `shadow_url` | str | 是 | - | 影子库 URL |
| `username` | str | 否 | - | 业务库用户名 |
| `shadow_username` | str | 否 | - | 影子库用户名 |
| `shadow_account_prefix` | str | 否 | PT_ | 账号前缀 |
| `business_shadow_tables` | dict | 否 | {} | 表名映射 |

---

## 📚 相关文档

- [配置指南](SHADOW_CONFIG_GUIDE.md) - 完整配置说明
- [配置示例](shadow_config_examples.yaml) - YAML 配置模板
- [使用示例](examples/shadow_config_usage.py) - Python 代码示例
- [沙箱验证指南](sandbox/VALIDATION_GUIDE.md) - 验证步骤

---

## ✅ 总结

现在 PyLinkAgent 的影子库配置支持：

- ✅ **YAML 配置文件** - 版本管理，便于审查
- ✅ **环境变量** - 容器化部署，CI/CD 集成
- ✅ **API 动态注册** - 运行时动态配置
- ✅ **远程配置中心** - 集中管理，多实例同步
- ✅ **代码注册** - 自定义逻辑，灵活控制

**配置不再写死，用户可以根据需求选择最适合的方式！**

---

**版本**: v1.0.0  
**创建时间**: 2026-04-07
