# PyLinkAgent 内网验证交付总结

## 交付日期
2026-04-11

## 交付内容概述

本次交付包含 PyLinkAgent 与 Takin-web 完整对接所需的所有组件、脚本和文档，专注于以下核心功能：
1. 心跳上报
2. 应用上传
3. 影子库配置拉取
4. 压测流量路由验证

---

## 核心功能验证

### 1. 心跳上报

**接口**: `POST /api/agent/heartbeat`

**实现文件**: 
- `pylinkagent/controller/external_api.py` - ExternalAPI.send_heartbeat()
- `takin_mock_server.py` - heartbeat() 端点

**验证方法**:
```bash
# 通过 Demo 应用发送心跳
curl http://localhost:8000/pylinkagent/heartbeat -X POST

# 直接调用 Mock Server
curl http://localhost:9999/api/agent/heartbeat -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "projectName": "demo-app",
    "agentId": "pylinkagent-001",
    "ipAddress": "127.0.0.1",
    "progressId": "12345",
    "curUpgradeBatch": "1",
    "agentStatus": "running",
    "uninstallStatus": 0,
    "dormantStatus": 0,
    "agentVersion": "1.0.0"
  }'
```

**验证标准**:
- [x] 接口返回 HTTP 200
- [x] `t_agent_report` 表有心跳记录
- [x] 心跳记录包含 application_name、agent_id、status 等字段

---

### 2. 应用上传

**接口**: `POST /api/application/center/app/info`

**实现文件**:
- `pylinkagent/controller/external_api.py` - ExternalAPI.upload_application_info()
- `takin_mock_server.py` - upload_application_info() 端点

**验证方法**:
```bash
curl http://localhost:9999/api/application/center/app/info -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "applicationName": "demo-app",
    "applicationDesc": "Demo Application",
    "useYn": 0,
    "accessStatus": 0,
    "switchStatus": "OPENED"
  }'
```

**验证标准**:
- [x] 接口返回 `{success: true, data: {applicationId: xxx}}`
- [x] `t_application_mnt` 表有应用记录

---

### 3. 影子库配置拉取

**接口**: `GET /api/link/ds/configs/pull?appName=xxx`

**实现文件**:
- `pylinkagent/controller/external_api.py` - ExternalAPI.fetch_shadow_database_config()
- `pylinkagent/controller/config_fetcher.py` - ConfigFetcher 定时拉取
- `takin_mock_server.py` - get_shadow_config() 端点

**验证方法**:
```bash
# 直接调用 Mock Server
curl "http://localhost:9999/api/link/ds/configs/pull?appName=demo-app"

# 通过 Demo 应用查看配置
curl http://localhost:8000/pylinkagent/config
```

**验证标准**:
- [x] 接口返回 `{success: true, data: {...shadow config...}}`
- [x] 配置数据包含 datasourceMediator 和 dataSources
- [x] ConfigFetcher 定时拉取（默认 60 秒）

---

### 4. 压测流量路由验证

**实现原理**:
- 通过 `x-pressure-test` Header 识别压测流量
- 压测流量路由到影子数据库
- 正常流量路由到主数据库

**验证方法**:
```bash
# 启动 Demo 应用
python demo_app.py

# 测试正常流量
curl http://localhost:8000/api/users

# 测试压测流量
curl http://localhost:8000/api/users -H "x-pressure-test: true"
```

**验证标准**:
- [x] 正常流量返回普通数据（如：`{"name": "张三"}`）
- [x] 压测流量返回影子数据（如：`{"name": "影子用户 1", "is_shadow": true}`）

---

## 文件清单

### 核心代码
```
pylinkagent/controller/
├── external_api.py          # ExternalAPI 接口 (~770 行)
│   ├── send_heartbeat()     # 心跳上报
│   ├── upload_application_info()  # 应用上传
│   └── fetch_shadow_database_config()  # 影子库配置拉取
└── config_fetcher.py        # 配置拉取器 (~330 行)
    └── ConfigFetcher        # 定时拉取影子库配置
```

### Takin-web Mock Server
```
PyLinkAgent/
└── takin_mock_server.py     # Takin-web Mock Server (~500 行)
    ├── POST /api/agent/heartbeat
    ├── POST /api/application/center/app/info
    ├── GET /api/link/ds/configs/pull
    ├── GET /api/agent/application/node/probe/operate
    └── POST /api/agent/application/node/probe/operateResult
```

### 数据库脚本
```
database/
├── end_to_end_init.sql      # 数据库初始化脚本 (~260 行)
│   ├── t_agent_report       # 探针心跳数据表
│   ├── t_application_mnt    # 应用管理表
│   ├── t_application_ds_manage  # 应用数据源配置表
│   ├── t_shadow_table_datasource  # 影子表数据源表
│   ├── t_shadow_job_config  # 影子 Job 配置表
│   └── t_application_node_probe  # 应用节点探针操作表
```

### 验证脚本
```
scripts/
├── run_verify.bat           # 一键验证脚本 (Windows)
├── run_verify.sh            # 一键验证脚本 (Linux)
└── end_to_end_verify.py     # 端到端验证脚本 (~450 行)
```

### Demo 应用
```
demo_app.py                  # Demo 应用 (~580 行)
├── GET /health              # 健康检查
├── GET /api/users           # 用户列表
├── GET /pylinkagent/status  # PyLinkAgent 状态
├── GET /pylinkagent/config  # 影子库配置
└── POST /pylinkagent/heartbeat  # 手动心跳
```

### 文档
```
├── INNER_NETWORK_VERIFICATION_GUIDE.md  # 内网验证完整指南
├── QUICK_START.md                       # 快速开始指南
├── DELIVERY_CHECKLIST.md                # 交付清单
└── DELIVERY_SUMMARY.md                  # 本文档
```

---

## 一键验证流程

### Windows 环境

```batch
cd D:\soft\agent\LinkAgent-main\PyLinkAgent
scripts\run_verify.bat localhost 3306 root your_password
```

### 验证流程说明

```
1. 检查 Python 环境
   │
   ├── 检查 Python 版本
   │
   └── 安装依赖 (fastapi, uvicorn, pymysql, httpx)

2. 初始化数据库
   │
   ├── 创建数据库 trodb
   │
   ├── 创建核心表 (6 张表)
   │
   └── 插入测试数据 (demo-app, test-app)

3. 启动 Takin-web Mock Server
   │
   ├── 启动 Mock Server (端口 9999)
   │
   └── 验证服务可访问性

4. 运行端到端验证
   │
   ├── 数据库验证 (表结构检查)
   │
   ├── 服务验证 (Mock Server 健康检查)
   │
   ├── 心跳上报验证 (发送心跳并检查数据库)
   │
   ├── 影子库配置拉取验证
   │
   └── 应用上传验证

5. 生成验证报告
   │
   └── 输出 verify_result.txt
```

---

## 验证通过标准

### 基础验证
- [x] MySQL 数据库可访问
- [x] 核心表已创建（6 张表）
- [x] 测试数据已插入
- [x] Takin-web Mock Server 可访问（端口 9999）

### 心跳验证
- [x] ExternalAPI 初始化成功
- [x] 心跳接口返回 HTTP 200
- [x] `t_agent_report` 表有心跳记录
- [x] 心跳记录包含正确的 agent_id 和 application_name

### 配置拉取验证
- [x] 影子库配置接口可访问
- [x] 配置数据解析正确
- [x] ConfigFetcher 定时拉取正常

### 压测路由验证
- [x] 正常流量路由到主库
- [x] 压测流量路由到影子库

---

## 数据库表关系

```
t_application_mnt (应用信息)
    ├── t_agent_report (心跳记录)
    │   └── 通过 application_id 关联
    │
    └── t_application_ds_manage (数据源配置)
        └── 通过 application_id 关联
```

---

## 接口对照表

### Takin-web 接口（原始 Java 项目）

| 接口 | 路径 | 方法 | 说明 |
|------|------|------|------|
| 心跳上报 | `/api/agent/heartbeat` | POST | 接收 Agent 心跳 |
| 应用上传 | `/api/application/center/app/info` | POST | 上传应用信息 |
| 影子库配置 | `/api/link/ds/configs/pull` | GET | 拉取影子库配置 |
| 命令拉取 | `/api/agent/application/node/probe/operate` | GET | 拉取操作命令 |
| 命令结果上报 | `/api/agent/application/node/probe/operateResult` | POST | 上报命令结果 |

### Mock Server 接口（Python 实现）

Mock Server 完全模拟上述接口，确保与原始 Takin-web 项目保持一致。

---

## 故障排查速查

| 问题 | 检查命令 | 解决方案 |
|------|----------|----------|
| 数据库连接失败 | `mysql -u root -p -e "SELECT 1"` | 确保 MySQL 服务运行 |
| Mock Server 不可访问 | `curl http://localhost:9999/health` | 重新启动 Mock Server |
| 心跳无记录 | `SELECT * FROM t_agent_report LIMIT 5` | 检查应用是否存在 |
| 影子库配置为空 | `SELECT * FROM t_application_ds_manage WHERE STATUS=0` | 插入测试配置 |
| PyLinkAgent 不可用 | `python -c "from pylinkagent.controller.external_api import ExternalAPI"` | 重新安装依赖 |

---

## 下一步

### 内网部署

1. 将 `PyLinkAgent` 目录复制到内网环境
2. 根据内网配置修改环境变量：
   ```bash
   export MANAGEMENT_URL=http://takin-web-internal:9999
   export APP_NAME=your-app-name
   export AGENT_ID=your-agent-id
   ```
3. 执行一键验证脚本

### 生产环境配置

1. 配置正确的 Takin-web 地址
2. 配置数据库连接信息
3. 配置应用名称和 Agent ID
4. 配置 ConfigFetcher 拉取间隔（默认 60 秒）

---

## 联系方式

如有问题，请参考以下文档：
- `INNER_NETWORK_VERIFICATION_GUIDE.md` - 内网验证完整指南
- `QUICK_START.md` - 快速开始指南
- `DELIVERY_CHECKLIST.md` - 交付清单

---

**交付版本**: 1.0.0  
**交付日期**: 2026-04-11  
**适用版本**: PyLinkAgent 2.0.0+, Takin-web 6.x+
