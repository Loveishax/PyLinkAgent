# PyLinkAgent 影子库配置指南

> **灵活的配置方案，支持多种配置来源**

---

## 📋 目录

1. [配置方式概览](#1-配置方式概览)
2. [YAML 配置文件](#2-yaml-配置文件)
3. [环境变量](#3-环境变量)
4. [API 动态注册](#4-api-动态注册)
5. [远程配置中心](#5-远程配置中心)
6. [配置优先级](#6-配置优先级)
7. [最佳实践](#7-最佳实践)

---

## 1. 配置方式概览

PyLinkAgent 支持 5 种影子库配置方式：

| 方式 | 适用场景 | 示例 |
|------|----------|------|
| **YAML 配置文件** | 固定配置，版本管理 | `shadow_config.yaml` |
| **环境变量** | 容器化部署，CI/CD | `PYLINKAGENT_SHADOW_*` |
| **API 动态注册** | 运行时动态配置 | `POST /configs/register` |
| **远程配置中心** | 集中管理，多实例 | 控制台下发 |
| **代码注册** | 自定义逻辑 | `register_config()` |

---

## 2. YAML 配置文件

### 2.1 配置文件示例

创建 `shadow_config.yaml`：

```yaml
# PyLinkAgent 影子库配置文件

shadow_databases:
  # 配置 1: 影子库模式
  - ds_type: 0
    url: jdbc:mysql://localhost:3306/test
    username: root
    password: root123
    shadow_url: jdbc:mysql://localhost:3307/shadow_test
    shadow_username: PT_root
    shadow_password: PT_root123
    shadow_account_prefix: PT_
    shadow_account_suffix: ""
    business_shadow_tables:
      users: shadow_users
      orders: shadow_orders
      products: shadow_products

  # 配置 2: 影子表模式
  - ds_type: 1
    url: jdbc:mysql://localhost:3306/app_db
    username: app_user
    password: app_pass
    shadow_account_prefix: shadow_
    business_shadow_tables:
      t_user: shadow_t_user
      t_order: shadow_t_order

  # 配置 3: 库 + 表模式
  - ds_type: 2
    url: jdbc:mysql://prod-db:3306/main
    username: prod_user
    password: prod_pass
    shadow_url: jdbc:mysql://shadow-db:3306/main
    shadow_username: PT_prod_user
    shadow_password: PT_prod_pass
    shadow_account_prefix: PT_
    business_shadow_tables:
      customers: PT_customers
      transactions: PT_transactions
```

### 2.2 加载配置文件

#### 方式 1：启动时指定

```python
from pylinkagent.shadow import init_config_center

# 初始化配置中心
config_center = init_config_center()
config_center._load_from_file("shadow_config.yaml")
```

#### 方式 2：环境变量指定路径

```bash
export PYLINKAGENT_SHADOW_CONFIG_FILE=shadow_config.yaml
python app.py
```

#### 方式 3：代码中加载

```python
from pylinkagent.shadow.config_center import load_from_file

count = load_from_file("/etc/pylinkagent/shadow.yaml")
print(f"加载了 {count} 个影子库配置")
```

---

## 3. 环境变量

### 3.1 JSON 数组格式（推荐）

适合容器化部署：

```bash
export PYLINKAGENT_SHADOW_CONFIGS='[
  {
    "ds_type": 0,
    "url": "jdbc:mysql://localhost:3306/test",
    "username": "root",
    "shadow_url": "jdbc:mysql://localhost:3307/shadow_test",
    "shadow_username": "PT_root",
    "shadow_account_prefix": "PT_",
    "business_shadow_tables": {
      "users": "shadow_users",
      "orders": "shadow_orders"
    }
  }
]'

python app.py
```

### 3.2 单个配置格式

适合简单场景：

```bash
# 基础配置
export PYLINKAGENT_SHADOW_URL=jdbc:mysql://localhost:3306/test
export PYLINKAGENT_SHADOW_SHADOW_URL=jdbc:mysql://localhost:3307/shadow_test

# 认证信息
export PYLINKAGENT_SHADOW_USERNAME=root
export PYLINKAGENT_SHADOW_PASSWORD=root123
export PYLINKAGENT_SHADOW_SHADOW_USERNAME=PT_root
export PYLINKAGENT_SHADOW_SHADOW_PASSWORD=PT_root123

# 账号前缀
export PYLINKAGENT_SHADOW_ACCOUNT_PREFIX=PT_

# 表名映射（逗号分隔）
export PYLINKAGENT_SHADOW_TABLE_MAPPING="users:shadow_users,orders:shadow_orders"

python app.py
```

### 3.3 Docker Compose 示例

```yaml
version: '3.8'

services:
  app:
    image: myapp:latest
    environment:
      - PYLINKAGENT_SHADOW_CONFIGS=[{"ds_type":0,"url":"jdbc:mysql://db:3306/test","shadow_url":"jdbc:mysql://shadow-db:3306/test","business_shadow_tables":{"users":"shadow_users"}}]
      - PYLINKAGENT_SHADOW_ACCOUNT_PREFIX=PT_
```

---

## 4. API 动态注册

### 4.1 启动 API 服务器

```python
from pylinkagent.shadow import init_config_center, ShadowConfigSource

# 配置 API 服务器
source = ShadowConfigSource(
    api_enabled=True,
    api_host="0.0.0.0",
    api_port=8081
)

config_center = init_config_center(source)
```

### 4.2 REST API 接口

#### 注册配置

```bash
curl -X POST http://localhost:8081/configs/register \
  -H "Content-Type: application/json" \
  -d '{
    "ds_type": 0,
    "url": "jdbc:mysql://localhost:3306/test",
    "username": "root",
    "shadow_url": "jdbc:mysql://localhost:3307/shadow_test",
    "shadow_username": "PT_root",
    "shadow_account_prefix": "PT_",
    "business_shadow_tables": {
      "users": "shadow_users",
      "orders": "shadow_orders"
    }
  }'
```

响应：
```json
{"status": "success", "message": "配置已注册"}
```

#### 删除配置

```bash
curl -X POST http://localhost:8081/configs/unregister \
  -H "Content-Type: application/json" \
  -d '{
    "url": "jdbc:mysql://localhost:3306/test",
    "username": "root"
  }'
```

#### 查询配置

```bash
curl http://localhost:8081/configs
```

响应：
```json
{
  "count": 1,
  "configs": [{
    "ds_type": 0,
    "url": "jdbc:mysql://localhost:3306/test",
    "shadow_url": "jdbc:mysql://localhost:3307/shadow_test",
    "business_shadow_tables": {"users": "shadow_users"}
  }]
}
```

#### 健康检查

```bash
curl http://localhost:8081/health
```

---

## 5. 远程配置中心

### 5.1 配置远程同步

```python
from pylinkagent.shadow import init_config_center, ShadowConfigSource

source = ShadowConfigSource(
    remote_enabled=True,
    remote_url="http://control-center:8080/api/shadow-configs",
    remote_api_key="your-api-key",
    remote_poll_interval=60  # 60 秒同步一次
)

config_center = init_config_center(source)
```

### 5.2 控制台集成

与 LinkAgent 控制平台集成，实现：

- 配置集中管理
- 配置版本控制
- 配置下发审计
- 多实例同步

---

## 6. 配置优先级

### 6.1 加载顺序

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

### 6.2 优先级示例

```bash
# 1. 配置文件设置
# shadow_config.yaml 中：shadow_account_prefix: "PT_"

# 2. 环境变量覆盖
export PYLINKAGENT_SHADOW_ACCOUNT_PREFIX="SHADOW_"

# 3. API 动态注册（最终值）
curl -X POST http://localhost:8081/configs/register \
  -d '{"shadow_account_prefix": "PRESSURE_"}'
```

最终使用：`PRESSURE_`

---

## 7. 最佳实践

### 7.1 开发环境

```python
# 使用 YAML 配置文件
from pylinkagent.shadow import init_config_center

config_center = init_config_center()
config_center._load_from_file("shadow_config.dev.yaml")
```

### 7.2 生产环境

```yaml
# docker-compose.yml
services:
  app:
    environment:
      # 使用环境变量，便于密钥管理
      - PYLINKAGENT_SHADOW_CONFIG_FILE=/etc/pylinkagent/shadow.yaml
    volumes:
      - ./shadow_config.prod.yaml:/etc/pylinkagent/shadow.yaml
    secrets:
      - shadow_db_password

secrets:
  shadow_db_password:
    external: true
```

### 7.3 多租户配置

```python
# 根据租户动态注册配置
def register_tenant_config(tenant_id: str, db_config: dict):
    config = ShadowDatabaseConfig(
        url=db_config["url"],
        shadow_url=db_config["shadow_url"],
        business_shadow_tables=db_config["table_mapping"],
    )
    register_config(config)

# 为每个租户配置影子库
for tenant in tenants:
    register_tenant_config(tenant.id, tenant.db_config)
```

### 7.4 配置热更新

```python
# 定时刷新配置
import threading
import time

def refresh_config():
    while True:
        time.sleep(60)
        # 从远程配置中心拉取最新配置
        config_center._start_remote_sync()

thread = threading.Thread(target=refresh_config, daemon=True)
thread.start()
```

---

## 8. 配置参考

### 8.1 完整配置参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `ds_type` | int | 否 | 0 | 0=影子库，1=影子表，2=库 + 表 |
| `url` | str | 是 | - | 业务库 URL |
| `username` | str | 否 | - | 业务库用户名 |
| `password` | str | 否 | - | 业务库密码 |
| `shadow_url` | str | 是 | - | 影子库 URL |
| `shadow_username` | str | 否 | - | 影子库用户名 |
| `shadow_password` | str | 否 | - | 影子库密码 |
| `shadow_account_prefix` | str | 否 | PT_ | 账号前缀 |
| `shadow_account_suffix` | str | 否 | "" | 账号后缀 |
| `business_shadow_tables` | dict | 否 | {} | 表名映射 |

### 8.2 环境变量前缀

所有环境变量使用统一前缀：

```
PYLINKAGENT_SHADOW_*
```

---

## 9. 故障排查

### 9.1 配置未加载

```bash
# 检查配置文件路径
ls -la shadow_config.yaml

# 检查环境变量
echo $PYLINKAGENT_SHADOW_CONFIGS

# 查看日志
export PYLINKAGENT_LOG_LEVEL=DEBUG
python app.py
```

### 9.2 API 服务器无法启动

```bash
# 检查端口占用
netstat -tlnp | grep 8081

# 更换端口
export PYLINKAGENT_SHADOW_API_PORT=8082
```

---

## 10. 相关文档

- [影子库实现总结](SHADOW_DB_IMPLEMENTATION_SUMMARY.md)
- [影子库验证报告](SHADOW_DB_VERIFICATION_REPORT.md)
- [沙箱验证指南](sandbox/VALIDATION_GUIDE.md)

---

**版本**: v1.0.0  
**最后更新**: 2026-04-07
