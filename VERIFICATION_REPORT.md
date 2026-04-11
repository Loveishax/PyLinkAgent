# PyLinkAgent 完整验证报告

**验证时间**: 2026-04-11  
**验证环境**: Windows 11, Python 3.x, MySQL 8.0  
**数据库配置**: root/123456@localhost:3306/trodb  

---

## 验证结果汇总

**总计：12/12 项验证通过 (100%)**

| 序号 | 验证项 | 结果 | 说明 |
|------|--------|------|------|
| 1 | 数据库表结构 | PASS | 4 个核心表已创建 |
| 2 | 测试应用数据 | PASS | demo-app 已插入 |
| 3 | 影子库配置数据 | PASS | 配置已插入 |
| 4 | Mock Server 健康检查 | PASS | 服务运行正常 |
| 5 | 心跳上报接口 | PASS | HTTP 200 |
| 6 | 应用上传接口 | PASS | applicationId=1 |
| 7 | 影子库配置拉取接口 | PASS | 配置拉取成功 |
| 8 | 心跳数据入库 | PASS | 1 条记录 |
| 9 | 数据库影子库配置 | PASS | 配置存在 |
| 10 | API 影子库配置拉取 | PASS | 拉取成功 |
| 11 | 正常流量路由 | PASS | 普通数据 |
| 12 | 压测流量路由 | PASS | 影子数据 |

---

## 验证环境

### 1. 数据库环境

```
MySQL: localhost:3306
用户：root
密码：123456
数据库：trodb
```

### 2. 服务端口

```
Takin-web Mock Server: http://localhost:9999
Demo Application: http://localhost:8000
```

### 3. 测试应用配置

```
应用名称：demo-app
Agent ID: pylinkagent-001
```

---

## 验证步骤详解

### 步骤 1: 数据库初始化验证

**验证目标**: 确认数据库表结构和测试数据已正确创建

**验证结果**:
- 表列表：`t_agent_report`, `t_application_mnt`, `t_application_ds_manage`, `t_application_node_probe`
- 测试应用 `demo-app` 已插入到 `t_application_mnt` 表
- 影子库配置已插入到 `t_application_ds_manage` 表

**数据库表结构**:

```sql
-- 1. 心跳表 (t_agent_report)
CREATE TABLE t_agent_report (
  id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  application_id bigint(20) DEFAULT '0',
  application_name varchar(64) DEFAULT '',
  agent_id varchar(600) NOT NULL,
  ip_address varchar(1024) DEFAULT '',
  status tinyint(2) DEFAULT '0',
  agent_version varchar(1024) DEFAULT '',
  simulator_version varchar(1024) DEFAULT NULL,
  gmt_create datetime DEFAULT CURRENT_TIMESTAMP,
  gmt_update datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  env_code varchar(100) DEFAULT 'test',
  tenant_id bigint(20) DEFAULT '1',
  PRIMARY KEY (id),
  UNIQUE KEY uni_app_agent (application_id,agent_id,env_code,tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 应用管理表 (t_application_mnt)
CREATE TABLE t_application_mnt (
  id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  APPLICATION_ID bigint(19) NOT NULL,
  APPLICATION_NAME varchar(50) NOT NULL,
  APPLICATION_DESC varchar(200) DEFAULT NULL,
  USE_YN int(1) DEFAULT '0',
  ACCESS_STATUS int(2) NOT NULL DEFAULT '0',
  SWITCH_STATUS varchar(255) NOT NULL DEFAULT 'OPENED',
  CREATE_TIME datetime DEFAULT CURRENT_TIMESTAMP,
  UPDATE_TIME datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  env_code varchar(20) DEFAULT 'test',
  tenant_id bigint(20) DEFAULT '1',
  PRIMARY KEY (id),
  UNIQUE KEY uk_app_name (APPLICATION_NAME)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 应用数据源配置表 (t_application_ds_manage)
CREATE TABLE t_application_ds_manage (
  ID bigint(20) NOT NULL AUTO_INCREMENT,
  APPLICATION_ID bigint(20) DEFAULT NULL,
  APPLICATION_NAME varchar(50) DEFAULT NULL,
  DB_TYPE tinyint(4) DEFAULT '0',
  DS_TYPE tinyint(4) DEFAULT '0',
  CONFIG longtext,
  PARSE_CONFIG longtext,
  STATUS tinyint(4) DEFAULT '0',
  CREATE_TIME timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UPDATE_TIME timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  env_code varchar(20) DEFAULT 'test',
  tenant_id bigint(20) DEFAULT '1',
  PRIMARY KEY (ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 步骤 2: Takin-web Mock Server 验证

**验证目标**: 确认 Mock Server 提供的 API 接口与原始 Takin-web 保持一致

**验证接口**:
1. `GET /health` - 健康检查
2. `POST /api/agent/heartbeat` - 心跳上报
3. `POST /api/application/center/app/info` - 应用上传
4. `GET /api/link/ds/configs/pull?appName=xxx` - 影子库配置拉取

**验证结果**:
- Mock Server 运行在 `http://localhost:9999`
- 所有接口返回 HTTP 200
- 接口响应格式与原始 Takin-web 一致

---

### 步骤 3: 心跳数据入库验证

**验证目标**: 确认探针心跳上报后，数据成功写入数据库

**数据库查询结果**:
```
ID=1, app=demo-app, agent=pylinkagent-001, ip=192.168.1.100, status=0, time=2026-04-11 14:34:51
```

**验证 SQL**:
```sql
SELECT id, application_name, agent_id, ip_address, status, gmt_update
FROM t_agent_report
ORDER BY gmt_update DESC
LIMIT 5;
```

---

### 步骤 4: 影子库配置拉取验证

**验证目标**: 确认探针能从后端拉取到影子库配置

**数据库配置内容**:
```
- dataSourceBusiness: jdbc:mysql://master-db:3306/demo_db
- dataSourcePerformanceTest: jdbc:mysql://shadow-db:3306/demo_db_shadow
```

**验证命令**:
```bash
curl "http://localhost:9999/api/link/ds/configs/pull?appName=demo-app"
```

---

### 步骤 5: 压测流量路由验证

**验证目标**: 确认压测流量（带 x-pressure-test header）路由到影子库

**正常流量测试**:
```bash
curl http://localhost:8000/api/users-with-header
```

**响应结果**:
```json
[{"id": 1, "name": "Alice", "email": "alice@example.com", "is_shadow": false}]
```

**压测流量测试**:
```bash
curl http://localhost:8000/api/users-with-header -H "x-pressure-test: true"
```

**响应结果**:
```json
[{"id": 1, "name": "Shadow Alice", "email": "shadow_alice@example.com", "is_shadow": true}]
```

**验证结论**: 压测流量正确路由到影子数据库

---

## 部署说明

### 内网部署步骤

#### 1. 准备环境

```bash
pip install pymysql httpx fastapi uvicorn
```

#### 2. 初始化数据库

```bash
cd PyLinkAgent
python init_db.py
```

#### 3. 启动 Takin-web Mock Server

```bash
python takin_mock_server.py --db-host localhost --db-port 3306 --db-user root --db-password 123456 --db-name trodb
```

#### 4. 启动 Demo 应用

```bash
python demo_app_simple.py
```

#### 5. 运行验证

```bash
python final_verify.py
```

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `takin_mock_server.py` | Takin-web 模拟器 |
| `demo_app_simple.py` | Demo 应用 |
| `init_db.py` | 数据库初始化脚本 |
| `final_verify.py` | 完整验证脚本 |

---

## 验证结论

本次验证完成了以下 6 项核心功能：

1. **数据库初始化** - 4 个核心表创建成功
2. **Takin-web Mock Server 部署** - 服务运行正常，API 接口一致
3. **探针心跳上报** - 心跳数据成功写入数据库
4. **影子库配置拉取** - 探针能从后端拉取影子库配置
5. **压测流量路由** - 压测流量正确路由到影子数据库
6. **验证文档输出** - 本文档可用于内网部署参考

**验证通过率：100%**

---

**文档版本**: 1.0  
**更新日期**: 2026-04-11
