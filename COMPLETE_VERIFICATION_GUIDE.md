# PyLinkAgent 完整验证流程指南

## 验证目标

本指南提供一套**完整的端到端验证流程**，包括：
1. ✅ 管理面心跳上报验证
2. ✅ 管理面影子配置下发与拉取验证
3. ✅ 影子探针验证（MySQL 影子库完整测试）

**预计验证时间**: 3-5 分钟

---

## 验证架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        验证环境                                  │
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │  PyLinkAgent │────▶│  管理侧服务   │────▶│   MySQL      │   │
│  │  (探针)      │◀────│  (9999)      │◀────│  (主库/影子库)│   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│         │                    │                      │           │
│         │                    │                      │           │
│         ▼                    ▼                      ▼           │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │  心跳上报     │     │  配置下发     │     │  影子路由     │   │
│  │  验证        │     │  验证        │     │  验证        │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 快速开始（推荐）

**一键式验证脚本**（最简单）:

```bash
cd PyLinkAgent

# 方式 1: 仅验证心跳和配置（不需要数据库）
python scripts/verify_all_in_one.py \
    --management-url http://192.168.1.100:9999 \
    --app-name my-app \
    --agent-id agent-001

# 方式 2: 完整验证（包含 MySQL 影子库）
python scripts/verify_all_in_one.py \
    --management-url http://192.168.1.100:9999 \
    --app-name my-app \
    --agent-id agent-001 \
    --master-db jdbc:mysql://192.168.1.50:3306/test_db \
    --shadow-db jdbc:mysql://192.168.1.51:3306/test_db_shadow \
    --db-username root \
    --db-password your-password
```

## 第一阶段：管理面心跳上报验证

### 1.1 环境准备

**检查清单**:
- [ ] 管理侧服务已启动（端口 9999）
- [ ] PyLinkAgent 代码已就绪
- [ ] Python 3.8+ 已安装
- [ ] 依赖库已安装（httpx, requests）

**安装依赖**:
```bash
cd PyLinkAgent
pip install httpx requests
```

### 1.2 运行心跳验证脚本

**脚本**: `scripts/verify_heartbeat_full.py`

```bash
# 快速验证
python scripts/verify_heartbeat_full.py http://<管理侧 IP>:9999

# 带应用信息
python scripts/verify_heartbeat_full.py \
    http://192.168.1.100:9999 \
    my-app \
    agent-001
```

### 1.3 验证输出示例

```
============================================================
PyLinkAgent 心跳上报验证
============================================================

管理侧地址：http://192.168.1.100:9999
应用名称：my-app
Agent ID: agent-001

[步骤 1/4] 检查管理侧连通性...
      [OK] 管理侧服务可访问

[步骤 2/4] 初始化 ExternalAPI...
      [OK] ExternalAPI 初始化成功

[步骤 3/4] 发送心跳请求...
      [OK] 心跳发送成功
      返回命令数：0

[步骤 4/4] 持续心跳监控 (30 秒)...
      [OK] 心跳 #1/3 - HTTP 200
      [OK] 心跳 #2/3 - HTTP 200
      [OK] 心跳 #3/3 - HTTP 200

============================================================
验证结果：[OK] 心跳上报验证通过
============================================================
```

### 1.4 验证通过标准

- [x] ExternalAPI 初始化成功
- [x] 心跳请求返回 HTTP 200
- [x] 持续心跳监控全部成功

---

## 第二阶段：影子配置下发与拉取验证

### 2.1 前置条件

**管理侧配置准备**:
1. 在管理侧创建应用配置
2. 配置影子库路由规则
3. 配置全局开关

### 2.2 运行配置验证脚本

**脚本**: `scripts/verify_config_full.py`

```bash
# 运行配置拉取验证
python scripts/verify_config_full.py http://<管理侧 IP>:9999
```

### 2.3 验证输出示例

```
============================================================
PyLinkAgent 配置拉取验证
============================================================

管理侧地址：http://192.168.1.100:9999
应用名称：my-app
Agent ID: agent-001

[步骤 1/3] 初始化 ExternalAPI...
      [OK] ExternalAPI 初始化成功

[步骤 2/3] 拉取配置数据...
      [OK] 配置拉取成功

      配置详情:
        - 影子库配置数：2
        - 全局开关数：5
        - Redis 影子配置数：0
        - URL 白名单数：10

      影子库配置示例:
        - datasource-1:
            master: jdbc:mysql://master:3306/app
            shadow: jdbc:mysql://shadow:3306/app_shadow
        - datasource-2:
            master: jdbc:mysql://master:3306/app
            shadow: jdbc:mysql://shadow:3306/app_shadow

[步骤 3/3] 验证配置变更通知...
      [OK] 配置拉取器启动成功
      [INFO] 等待 35 秒观察配置拉取...
      [OK] 配置拉取器运行正常

============================================================
验证结果：[OK] 配置拉取验证通过
============================================================
```

### 2.4 验证通过标准

- [x] 配置拉取成功
- [x] 影子库配置数据正确
- [x] 全局开关配置正确
- [x] 配置变更通知机制正常

---

## 第三阶段：影子探针验证（MySQL）

### 3.1 环境准备

**需要的基础设施**:
```
主库 MySQL:    jdbc:mysql://<主库 IP>:3306/test_db
影子库 MySQL:  jdbc:mysql://<影子库 IP>:3306/test_db_shadow
```

**配置影子库表结构**:
```sql
-- 在影子库创建相同的表结构
CREATE DATABASE IF NOT EXISTS test_db_shadow;
USE test_db_shadow;

CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 配置管理侧影子库

**在管理侧配置影子库路由**:

1. 登录管理侧前端（http://<管理侧 IP>:3002）
2. 进入"配置管理" -> "影子库配置"
3. 添加数据源配置：

```json
{
    "datasourceName": "test-datasource",
    "master": {
        "jdbcUrl": "jdbc:mysql://<主库 IP>:3306/test_db",
        "username": "root",
        "password": "your-password"
    },
    "shadow": {
        "jdbcUrl": "jdbc:mysql://<影子库 IP>:3306/test_db_shadow",
        "username": "root",
        "password": "your-password"
    },
    "shadowTableRules": [
        {
            "logicTable": "users",
            "shadowTable": "users"
        }
    ]
}
```

### 3.3 运行影子探针验证脚本

**脚本**: `scripts/verify_shadow_mysql.py`

```bash
# 设置环境变量
export MANAGEMENT_URL=http://<管理侧 IP>:9999
export APP_NAME=my-app
export AGENT_ID=agent-001

# 主库配置
export MASTER_DB_URL=jdbc:mysql://<主库 IP>:3306/test_db
export MASTER_DB_USERNAME=root
export MASTER_DB_PASSWORD=your-password

# 影子库配置
export SHADOW_DB_URL=jdbc:mysql://<影子库 IP>:3306/test_db_shadow
export SHADOW_DB_USERNAME=root
export SHADOW_DB_PASSWORD=your-password

# 运行验证
python scripts/verify_shadow_mysql.py
```

### 3.4 验证输出示例

```
============================================================
PyLinkAgent MySQL 影子探针验证
============================================================

主库：jdbc:mysql://192.168.1.50:3306/test_db
影子库：jdbc:mysql://192.168.1.51:3306/test_db_shadow

[步骤 1/5] 初始化 PyLinkAgent...
      [OK] ExternalAPI 初始化成功
      [OK] 配置拉取成功

[步骤 2/5] 连接数据库...
      [OK] 主库连接成功
      [OK] 影子库连接成功

[步骤 3/5] 验证 Pradar 链路追踪...
      [OK] TraceID 生成正常：000135671234567...
      [OK] 上下文管理正常

[步骤 4/5] 验证影子路由...
      [INFO] 执行主库写入：INSERT INTO users (name, email) VALUES ('test', 'test@example.com')
      [OK] 主库写入成功 - ID: 1
      [INFO] 影子库同步写入验证...
      [OK] 影子库数据一致

[步骤 5/5] 验证压测流量标识...
      [INFO] 设置压测标识...
      [OK] 压测流量正确路由到影子库

============================================================
验证结果：[OK] MySQL 影子探针验证通过
============================================================

详细结果:
  - 主库写入次数：3
  - 影子库写入次数：3
  - 路由准确率：100%
  - 平均响应时间：15ms
```

### 3.5 验证通过标准

- [x] Pradar 链路追踪正常
- [x] 主库连接成功
- [x] 影子库连接成功
- [x] 影子路由规则生效
- [x] 压测流量正确路由到影子库
- [x] 主库和影子库数据一致

---

## 完整验证流程（一键执行）

**脚本**: `scripts/verify_all_in_one.py`

```bash
# 一键执行所有验证（约 3 分钟）
python scripts/verify_all_in_one.py \
    --management-url http://192.168.1.100:9999 \
    --app-name my-app \
    --agent-id agent-001 \
    --master-db jdbc:mysql://192.168.1.50:3306/test_db \
    --shadow-db jdbc:mysql://192.168.1.51:3306/test_db_shadow \
    --db-username root \
    --db-password your-password
```

### 输出示例

```
============================================================
PyLinkAgent 完整验证流程（一键式）
============================================================

验证配置:
  管理侧地址：http://192.168.1.100:9999
  应用名称：my-app
  Agent ID: agent-001
  主库：jdbc:mysql://192.168.1.50:3306/test_db
  影子库：jdbc:mysql://192.168.1.51:3306/test_db_shadow

============================================================
阶段 1/3: 心跳上报验证
============================================================
[OK] 心跳上报验证通过

============================================================
阶段 2/3: 配置拉取验证
============================================================
[OK] 配置拉取验证通过
      影子库配置：2 个

============================================================
阶段 3/3: MySQL 影子探针验证
============================================================
[OK] MySQL 影子探针验证通过
      主库写入：3 次
      影子库写入：3 次

============================================================
最终结果：[OK] 所有验证通过
============================================================
```

---

## 附录

### A. 验证脚本清单

| 脚本 | 阶段 | 耗时 |
|------|------|------|
| `scripts/verify_heartbeat_full.py` | 阶段 1 | 30 秒 |
| `scripts/verify_config_full.py` | 阶段 2 | 40 秒 |
| `scripts/verify_shadow_mysql.py` | 阶段 3 | 60 秒 |
| `scripts/verify_all_in_one.py` | 全部 | 3 分钟 |

### B. 常见问题

#### Q1: 心跳返回 500 错误
**A**: 管理侧数据库表结构可能不完整，但心跳功能仍正常工作。

#### Q2: 配置拉取返回空
**A**: 管理侧没有配置影子库数据，需要在管理侧前端配置。

#### Q3: 影子库路由不生效
**A**: 检查配置是否正确，确保压测标识已设置。

### C. 验证报告模板

验证完成后，生成验证报告：

```markdown
# PyLinkAgent 验证报告

## 验证时间
2026-XX-XX

## 验证环境
- 管理侧：http://192.168.1.100:9999
- 主库：jdbc:mysql://192.168.1.50:3306/test_db
- 影子库：jdbc:mysql://192.168.1.51:3306/test_db_shadow

## 验证结果
| 阶段 | 验证项 | 结果 |
|------|--------|------|
| 阶段 1 | 心跳上报 | [OK] |
| 阶段 2 | 配置拉取 | [OK] |
| 阶段 3 | MySQL 影子探针 | [OK] |

## 结论
PyLinkAgent 可以正常与管理侧通信，影子库路由功能正常。
```

---

**文档版本**: 1.0.0  
**更新日期**: 2026-04-10  
**适用版本**: PyLinkAgent 1.0.0+
