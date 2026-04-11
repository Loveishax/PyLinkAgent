# PyLinkAgent 内网验证完整指南

## 概述

本指南提供 PyLinkAgent 与 Takin-web 对接的完整验证流程。

### 验证目标

1. ✅ 数据库初始化（心跳表、应用表、影子库配置表）
2. ✅ Takin-web Mock Server 部署（模拟真实 Takin-web 接口）
3. ✅ PyLinkAgent 探针挂载与心跳上报
4. ✅ 影子库配置拉取验证
5. ✅ 压测流量路由验证

---

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | PyLinkAgent 运行环境 |
| MySQL | 5.7+ | 数据库 |
| pip | - | Python 包管理 |

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

### 步骤 1：安装 Python 依赖

```bash
cd D:\soft\agent\LinkAgent-main\PyLinkAgent
pip install fastapi uvicorn pymysql httpx
```

### 步骤 2：初始化 MySQL 数据库

```bash
# 连接到 MySQL
mysql -u root -p

# 创建数据库
CREATE DATABASE IF NOT EXISTS trodb DEFAULT CHARACTER SET utf8mb4;
USE trodb;

# 执行初始化脚本
source D:\soft\agent\LinkAgent-main\PyLinkAgent\database\end_to_end_init.sql
```

### 步骤 3：验证数据库初始化

```sql
USE trodb;

-- 检查表是否存在
SHOW TABLES LIKE 't_%';

-- 检查测试应用
SELECT APPLICATION_ID, APPLICATION_NAME FROM t_application_mnt;

-- 检查影子库配置
SELECT ID, APPLICATION_NAME FROM t_application_ds_manage WHERE STATUS = 0;
```

预期输出：
```
+------------------+
| APPLICATION_NAME |
+------------------+
| demo-app         |
| test-app         |
+------------------+
```

### 步骤 4：启动 Takin-web Mock Server

```bash
cd D:\soft\agent\LinkAgent-main\PyLinkAgent
python takin_mock_server.py --port 9999 --db-host localhost --db-port 3306 --db-user root --db-name trodb
```

验证 Mock Server 启动：

```bash
curl http://localhost:9999/health
```

预期响应：
```json
{"status": "healthy", "timestamp": "2026-04-11T10:00:00"}
```

### 步骤 5：配置环境变量

```bash
# Windows (cmd)
set MANAGEMENT_URL=http://localhost:9999
set APP_NAME=demo-app
set AGENT_ID=pylinkagent-001

# Windows (PowerShell)
$env:MANAGEMENT_URL="http://localhost:9999"
$env:APP_NAME="demo-app"
$env:AGENT_ID="pylinkagent-001"

# Linux/Mac
export MANAGEMENT_URL=http://localhost:9999
export APP_NAME=demo-app
export AGENT_ID=pylinkagent-001
```

### 步骤 6：启动 Demo 应用

```bash
cd D:\soft\agent\LinkAgent-main\PyLinkAgent
python demo_app.py
```

应用将在 http://localhost:8000 启动。

### 步骤 7：验证 PyLinkAgent 状态

```bash
# 检查健康状态
curl http://localhost:8000/health

# 检查 PyLinkAgent 状态
curl http://localhost:8000/pylinkagent/status
```

预期响应：
```json
{
  "available": true,
  "app_name": "demo-app",
  "agent_id": "pylinkagent-001",
  "management_url": "http://localhost:9999"
}
```

---

## 功能验证

### 1. 心跳上报验证

```bash
# 手动发送心跳
curl http://localhost:8000/pylinkagent/heartbeat -X POST -H "Content-Type: application/json"

# 查看数据库中的心跳记录
mysql -u root -p -e "SELECT * FROM trodb.t_agent_report WHERE application_name='demo-app' ORDER BY gmt_update DESC LIMIT 5;"
```

**预期结果**：
- 心跳接口返回成功
- `t_agent_report` 表中有记录

### 2. 影子库配置拉取验证

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

### 3. 压测流量路由验证

```bash
# 测试正常流量
curl http://localhost:8000/api/users

# 测试压测流量
curl http://localhost:8000/api/users -H "x-pressure-test: true"

# 使用 Pradar 标识
curl http://localhost:8000/api/users -H "x-pradar-trace: pressure-test"
```

**预期结果**：
- 正常流量返回普通数据：`[{"id": 1, "name": "张三", ...}]`
- 压测流量返回影子数据：`[{"id": 1, "name": "影子用户 1", "is_shadow": true, ...}]`

### 4. 查看心跳记录

```bash
# 查看最近的心跳记录
mysql -u root -p -e "
SELECT 
    id,
    application_name,
    agent_id,
    status,
    agent_version,
    gmt_update
FROM trodb.t_agent_report 
ORDER BY gmt_update DESC 
LIMIT 10;
"
```

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
# 检查 MySQL 服务是否运行
netstat -an | grep 3306

# 测试连接
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
# 检查端口是否被占用
netstat -an | grep 9999

# 查看 Mock Server 日志
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
SELECT ID, APPLICATION_NAME, CONFIG FROM t_application_ds_manage WHERE STATUS=0;

-- 如果没有配置，插入测试配置
INSERT INTO t_application_ds_manage
(APPLICATION_ID, APPLICATION_NAME, DB_TYPE, DS_TYPE, CONFIG, PARSE_CONFIG, STATUS, env_code, tenant_id)
VALUES
(1, 'demo-app', 0, 0, '{
  "datasourceMediator": {
    "dataSourceBusiness": "dataSourceBusiness",
    "dataSourcePerformanceTest": "dataSourcePerformanceTest"
  },
  "dataSources": [
    {
      "id": "dataSourceBusiness",
      "url": "jdbc:mysql://localhost:3306/demo_db",
      "username": "root"
    },
    {
      "id": "dataSourcePerformanceTest",
      "url": "jdbc:mysql://localhost:3306/demo_db_shadow",
      "username": "root"
    }
  ]
}', '{}', 0, NOW(), NOW(), 'test', 1);
```

### 问题 5：PyLinkAgent 模块不可用

**现象**：`/pylinkagent/status` 返回 `available: false`

**解决**：
```bash
# 重新安装依赖
pip install httpx pymysql

# 检查导入
python -c "from pylinkagent.controller.external_api import ExternalAPI; print('OK')"
```

---

## 文件清单

```
D:\soft\agent\LinkAgent-main\PyLinkAgent\
├── takin_mock_server.py         # Takin-web Mock Server (与原始接口一致)
├── demo_app.py                   # Demo 应用（含 PyLinkAgent 集成）
├── database/
│   └── end_to_end_init.sql       # 数据库初始化脚本
├── scripts/
│   ├── run_verify.bat            # 一键验证脚本 (Windows)
│   ├── run_verify.sh             # 一键验证脚本 (Linux)
│   └── end_to_end_verify.py      # 端到端验证脚本
└── pylinkagent/controller/
    ├── external_api.py           # ExternalAPI 接口（心跳、配置拉取等）
    └── config_fetcher.py         # 配置拉取器（定时拉取影子库配置）
```

---

## 数据库表结构

### t_agent_report - 探针心跳数据表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| application_id | bigint | 应用 ID |
| application_name | varchar | 应用名称 |
| agent_id | varchar | Agent 唯一标识 |
| ip_address | varchar | 节点 IP 地址 |
| status | tinyint | 节点状态 (0:未知，1:启动中，2:升级待重启，3:运行中，4:异常，5:休眠，6:卸载) |
| agent_version | varchar | Agent 版本 |
| gmt_update | datetime | 更新时间 |

### t_application_mnt - 应用管理表

| 字段 | 类型 | 说明 |
|------|------|------|
| APPLICATION_ID | bigint | 应用 ID |
| APPLICATION_NAME | varchar | 应用名称 |
| ACCESS_STATUS | int | 接入状态 (0:正常，1:待配置，2:待检测，3:异常) |
| SWITCH_STATUS | varchar | 开关状态 (OPENED/CLOSED) |

### t_application_ds_manage - 应用数据源配置表

| 字段 | 类型 | 说明 |
|------|------|------|
| ID | bigint | 主键 |
| APPLICATION_ID | bigint | 应用 ID |
| APPLICATION_NAME | varchar | 应用名称 |
| DS_TYPE | tinyint | 方案类型 (0:影子库，1:影子表) |
| CONFIG | longtext | 配置内容 (JSON 格式) |
| STATUS | tinyint | 状态 (0:启用，1:禁用) |

---

## 总结

完成以上所有步骤后，您应该能够：

1. ✅ 看到 PyLinkAgent 成功连接 Takin-web Mock Server
2. ✅ 心跳数据成功入库（`t_agent_report`）
3. ✅ 影子库配置成功拉取
4. ✅ 压测流量正确路由到影子库

**文档版本**: 1.0.0  
**创建日期**: 2026-04-11  
**适用版本**: PyLinkAgent 2.0.0+, Takin-web Mock Server 6.0.0
