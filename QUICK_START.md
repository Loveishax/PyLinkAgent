# PyLinkAgent 内网验证快速指南

## 概述

本指南提供 PyLinkAgent 在内网环境中的完整验证流程，包括：
1. ✅ 数据库初始化（心跳表、应用表、影子库配置表）
2. ✅ Takin-web Mock Server 部署（模拟真实 Takin-web 接口）
3. ✅ PyLinkAgent 探针挂载与心跳上报
4. ✅ 影子库配置拉取验证
5. ✅ 压测流量路由验证

---

## 快速开始（一键验证）

### Windows 环境

打开命令行，执行：

```batch
cd D:\soft\agent\LinkAgent-main\PyLinkAgent
scripts\run_verify.bat localhost 3306 root your_password
```

### Linux/Mac 环境

```bash
cd /path/to/PyLinkAgent
bash scripts/run_verify.sh localhost 3306 root your_password
```

---

## 手动验证步骤

### 步骤 1：准备环境

确保以下服务已启动：
- **MySQL** (端口 3306)
- **Python 3.8+**

### 步骤 2：初始化数据库

```bash
cd D:\soft\agent\LinkAgent-main\PyLinkAgent
mysql -u root -p < database/end_to_end_init.sql
```

验证数据库初始化：

```sql
mysql -u root -p
USE trodb;

-- 检查表是否存在
SHOW TABLES LIKE 't_%';

-- 检查测试应用
SELECT APPLICATION_ID, APPLICATION_NAME FROM t_application_mnt;

-- 检查影子库配置
SELECT ID, APPLICATION_NAME, CONFIG FROM t_application_ds_manage;
```

### 步骤 3：启动 Takin-web Mock Server

```bash
cd D:\soft\agent\LinkAgent-main\PyLinkAgent
python takin_mock_server.py --port 9999 --db-host localhost --db-port 3306 --db-user root --db-password your_password
```

验证 Mock Server 启动：

```bash
curl http://localhost:9999/health
```

预期响应：
```json
{"status": "healthy", "timestamp": "2026-04-11T10:00:00"}
```

### 步骤 4：安装 PyLinkAgent 依赖

```bash
cd D:\soft\agent\LinkAgent-main\PyLinkAgent
pip install -r requirements.txt
pip install httpx pymysql
```

### 步骤 5：配置环境变量

```bash
# Windows
set MANAGEMENT_URL=http://localhost:9999
set APP_NAME=demo-app
set AGENT_ID=pylinkagent-001

# Linux/Mac
export MANAGEMENT_URL=http://localhost:9999
export APP_NAME=demo-app
export AGENT_ID=pylinkagent-001
```

### 步骤 6：运行验证脚本

```bash
python scripts/end_to_end_verify.py \
    --mysql-host localhost \
    --mysql-port 3306 \
    --mysql-user root \
    --mysql-password your_password \
    --mysql-db trodb \
    --takin-url http://localhost:9999 \
    --app-name demo-app \
    --agent-id pylinkagent-001
```

### 步骤 7：启动 Demo 应用

```bash
cd D:\soft\agent\LinkAgent-main\PyLinkAgent
python demo_app.py
```

验证应用启动：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/pylinkagent/status
```

### 步骤 8：验证功能

#### 8.1 心跳上报验证

```bash
# 手动发送心跳
curl http://localhost:8000/pylinkagent/heartbeat -X POST

# 查看数据库中的心跳记录
mysql -u root -p -e "SELECT * FROM trodb.t_agent_report WHERE application_name='demo-app' ORDER BY gmt_update DESC LIMIT 5;"
```

**预期结果**：
- 心跳接口返回成功
- `t_agent_report` 表中有记录

#### 8.2 影子库配置拉取验证

```bash
# 查看影子库配置
curl http://localhost:8000/pylinkagent/config
```

**预期结果**：
```json
{
  "has_shadow_config": true,
  "shadow_databases": {
    "dataSourceBusiness": {
      "url": "jdbc:mysql://master-db:3306/demo_db",
      "shadow_url": "jdbc:mysql://shadow-db:3306/demo_db_shadow",
      "username": "root"
    }
  }
}
```

#### 8.3 压测流量路由验证

```bash
# 测试正常流量
curl http://localhost:8000/api/users

# 测试压测流量
curl http://localhost:8000/api/users -H "x-pressure-test: true"

# 使用 Pradar 标识
curl http://localhost:8000/api/users -H "x-pradar-trace: pressure-test"
```

**预期结果**：
- 正常流量返回普通数据
- 压测流量返回影子数据（带有"影子"标识）

---

## 验证检查清单

### 基础验证

- [ ] MySQL 数据库可访问
- [ ] 核心表已创建（`t_agent_report`, `t_application_mnt`, `t_application_ds_manage`）
- [ ] 测试数据已插入
- [ ] Takin-web Mock Server 可访问（端口 9999）

### 心跳验证

- [ ] ExternalAPI 初始化成功
- [ ] 心跳接口返回 HTTP 200
- [ ] `t_agent_report` 表有心跳记录
- [ ] 心跳记录包含正确的 agent_id 和 application_name

### 配置拉取验证

- [ ] 影子库配置接口可访问
- [ ] 配置数据解析正确
- [ ] ConfigFetcher 定时拉取正常

### 压测路由验证

- [ ] 正常流量路由到主库
- [ ] 压测流量路由到影子库
- [ ] SQL 重写功能正常

---

## 接口速查表

### Takin-web Mock Server 接口

| 接口 | 路径 | 方法 | 说明 |
|------|------|------|------|
| 健康检查 | `/health` | GET | 服务健康状态 |
| 心跳上报 | `/api/agent/heartbeat` | POST | 接收 Agent 心跳，保存到数据库 |
| 应用上传 | `/api/application/center/app/info` | POST | 上传应用信息 |
| 影子库配置 | `/api/link/ds/configs/pull?appName=xxx` | GET | 拉取影子库配置 |
| 命令拉取 | `/api/agent/application/node/probe/operate` | GET | 拉取操作命令 |
| 命令结果上报 | `/api/agent/application/node/probe/operateResult` | POST | 上报命令执行结果 |

### PyLinkAgent Demo 接口

| 接口 | 路径 | 方法 | 说明 |
|------|------|------|------|
| 首页 | `/` | GET | 应用首页 |
| 健康检查 | `/health` | GET | 健康状态 |
| 用户列表 | `/api/users` | GET | 用户列表 |
| PyLinkAgent 状态 | `/pylinkagent/status` | GET | 探针状态 |
| 影子库配置 | `/pylinkagent/config` | GET | 配置查询 |
| 手动心跳 | `/pylinkagent/heartbeat` | POST | 发送心跳 |

---

## 故障排查

### 问题 1：数据库连接失败

**现象**：
```
pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")
```

**解决**：
```bash
# 检查 MySQL 服务
netstat -an | grep 3306

# 检查连接
mysql -u root -p -e "SELECT 1"

# 确认数据库存在
mysql -u root -p -e "SHOW DATABASES LIKE 'trodb'"
```

### 问题 2：Mock Server 不可访问

**现象**：
```
curl: (7) Failed to connect to localhost port 9999
```

**解决**：
```bash
# 检查端口
netstat -an | grep 9999

# 查看启动日志
# 重新启动 Mock Server
python takin_mock_server.py --port 9999
```

### 问题 3：心跳无记录

**现象**：心跳上报成功但数据库无记录

**解决**：
```sql
-- 检查应用是否存在
SELECT * FROM t_application_mnt WHERE APPLICATION_NAME = 'demo-app';

-- 如果不存在，插入应用
INSERT INTO t_application_mnt 
(APPLICATION_ID, APPLICATION_NAME, APPLICATION_DESC, USE_YN, ACCESS_STATUS, SWITCH_STATUS, env_code, tenant_id)
VALUES (1, 'demo-app', 'Demo Application', 0, 0, 'OPENED', 'test', 1);
```

### 问题 4：影子库配置为空

**现象**：`/pylinkagent/config` 返回空配置

**解决**：
```sql
-- 检查配置是否存在
SELECT ID, APPLICATION_NAME FROM t_application_ds_manage WHERE STATUS=0;

-- 插入配置
INSERT INTO t_application_ds_manage
(APPLICATION_ID, APPLICATION_NAME, DB_TYPE, DS_TYPE, CONFIG, PARSE_CONFIG, STATUS, env_code, tenant_id)
VALUES
(1, 'demo-app', 0, 0, '{"datasourceMediator": {...}}', '{}', 0, 'test', 1);
```

---

## 文件清单

```
D:\soft\agent\LinkAgent-main\PyLinkAgent\
├── takin_mock_server.py         # Takin-web Mock Server
├── demo_app.py                   # Demo 应用
├── database/
│   └── end_to_end_init.sql       # 数据库初始化脚本
├── scripts/
│   ├── run_verify.bat            # 一键验证脚本 (Windows)
│   ├── run_verify.sh             # 一键验证脚本 (Linux)
│   └── end_to_end_verify.py      # 端到端验证脚本
└── pylinkagent/controller/
    ├── external_api.py           # ExternalAPI 接口
    └── config_fetcher.py         # 配置拉取器
```

---

## 总结

完成以上所有步骤后，您应该能够：

1. ✅ 看到 PyLinkAgent 成功连接 Takin-web Mock Server
2. ✅ 心跳数据成功入库（`t_agent_report`）
3. ✅ 影子库配置成功拉取
4. ✅ 压测流量正确路由到影子库

**文档版本**: 1.0.0  
**创建日期**: 2026-04-11  
**适用版本**: PyLinkAgent 2.0.0+, Takin-web 6.x+
