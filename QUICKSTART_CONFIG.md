# PyLinkAgent 影子库配置快速上手

> **5 分钟学会如何灵活配置影子库**

---

## 🚀 第一步：选择配置方式

根据你的使用场景选择：

| 场景 | 推荐方式 | 难度 |
|------|----------|------|
| 本地开发 | YAML 配置文件 | ⭐ |
| Docker 部署 | 环境变量 | ⭐⭐ |
| 生产环境 | 远程配置中心 | ⭐⭐⭐ |
| 动态场景 | API 动态注册 | ⭐⭐ |

---

## 📝 方式 1：YAML 配置文件（最简单）

### 1. 创建配置文件

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

### 2. 加载配置

```python
from pylinkagent.shadow import init_config_center, ShadowConfigSource

source = ShadowConfigSource(config_file="shadow_config.yaml")
config_center = init_config_center(source)

print(f"加载了 {len(config_center.get_all_configs())} 个配置")
```

**完成！** ✅

---

## 🐳 方式 2：环境变量（Docker 推荐）

### 1. 设置环境变量

```bash
export PYLINKAGENT_SHADOW_CONFIGS='[{
  "ds_type": 0,
  "url": "jdbc:mysql://db:3306/test",
  "shadow_url": "jdbc:mysql://shadow-db:3306/test",
  "business_shadow_tables": {"users": "shadow_users"}
}]'
```

### 2. 启动应用

```bash
python app.py
```

配置会自动加载！ ✅

### Docker Compose 示例

```yaml
services:
  app:
    image: myapp:latest
    environment:
      - PYLINKAGENT_SHADOW_CONFIGS=[{"ds_type":0,"url":"jdbc:mysql://db:3306/test","shadow_url":"jdbc:mysql://shadow-db:3306/test","business_shadow_tables":{"users":"shadow_users"}}]
```

---

## 🔧 方式 3：API 动态注册（最灵活）

### 1. 启动 API 服务器

```python
from pylinkagent.shadow import init_config_center, ShadowConfigSource

source = ShadowConfigSource(
    api_enabled=True,
    api_port=8081
)
config_center = init_config_center(source)
```

### 2. 通过 API 注册配置

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

### 3. 查询配置

```bash
curl http://localhost:8081/configs
```

**完成！** ✅

---

## 💻 方式 4：代码注册（最灵活）

```python
from pylinkagent.shadow import (
    ShadowDatabaseConfig,
    get_config_center
)

center = get_config_center()

config = ShadowDatabaseConfig(
    ds_type=0,
    url="jdbc:mysql://localhost:3306/test",
    shadow_url="jdbc:mysql://localhost:3307/shadow_test",
    business_shadow_tables={"users": "shadow_users"}
)

center.register_config(config)
```

**完成！** ✅

---

## 🎯 完整示例：FastAPI 集成

```python
from fastapi import FastAPI
from pylinkagent.shadow import init_config_center, ShadowConfigSource, ShadowDatabaseConfig

app = FastAPI()

# 初始化配置中心
config_center = init_config_center(ShadowConfigSource(
    api_enabled=True,
    api_port=8081
))

@app.post("/shadow/config")
def register_shadow_config(config_data: dict):
    """注册影子库配置"""
    config = ShadowDatabaseConfig(
        ds_type=config_data.get("ds_type", 0),
        url=config_data["url"],
        shadow_url=config_data["shadow_url"],
        business_shadow_tables=config_data.get("business_shadow_tables", {})
    )
    config_center.register_config(config)
    return {"status": "success", "message": "配置已注册"}

@app.get("/shadow/configs")
def list_configs():
    """列出所有配置"""
    configs = config_center.get_all_configs()
    return {"count": len(configs), "configs": [
        {"url": c.url, "shadow_url": c.shadow_url, "tables": c.business_shadow_tables}
        for c in configs
    ]}
```

---

## 📊 配置参数说明

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `ds_type` | 数据源类型 | 0 | 0=影子库，1=影子表，2=库 + 表 |
| `url` | 业务库 URL | - | `jdbc:mysql://localhost:3306/test` |
| `shadow_url` | 影子库 URL | - | `jdbc:mysql://localhost:3307/shadow_test` |
| `username` | 业务库用户名 | - | `root` |
| `shadow_username` | 影子库用户名 | - | `PT_root` |
| `shadow_account_prefix` | 账号前缀 | `PT_` | `PT_` |
| `business_shadow_tables` | 表名映射 | `{}` | `{"users": "shadow_users"}` |

---

## ✅ 验证配置

```python
from pylinkagent.shadow import get_config, get_config_center

# 获取所有配置
configs = get_config_center().get_all_configs()
print(f"共有 {len(configs)} 个配置")

# 查询特定配置
config = get_config("jdbc:mysql://localhost:3306/test")
if config:
    print(f"找到配置：{config}")
else:
    print("未找到配置")
```

---

## 📚 更多资源

- [完整配置指南](SHADOW_CONFIG_GUIDE.md) - 详细文档
- [配置示例](shadow_config_examples.yaml) - YAML 模板
- [使用示例](examples/shadow_config_usage.py) - 代码示例

---

## 🆘 常见问题

### Q: 配置文件在哪？
A: 可以放在任何位置，通过 `config_file` 参数指定路径。

### Q: 多个配置如何优先级？
A: API 动态注册 > 远程配置 > 环境变量 > YAML 文件

### Q: 配置可以热更新吗？
A: 可以，使用 API 动态注册或远程配置中心支持热更新。

### Q: 如何删除配置？
A: 使用 API：`POST /configs/unregister` 或代码：`center.unregister_config(url)`

---

**现在你可以灵活配置影子库了！** 🎉
