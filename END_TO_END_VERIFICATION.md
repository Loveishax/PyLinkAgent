# PyLinkAgent 端到端验证指南

## 概述

本指南说明如何在完整环境中验证 PyLinkAgent 与 Takin-web 的对接，包括：
1. 数据库表创建和测试数据准备
2. Takin-web 服务部署
3. PyLinkAgent 探针挂载
4. 心跳上报验证
5. 影子库配置拉取验证
6. 压测流量路由验证

## 目录

1. [环境要求](#环境要求)
2. [数据库配置](#数据库配置)
3. [Takin-web 部署](#takin-web-部署)
4. [PyLinkAgent 配置](#pylinkagent-配置)
5. [验证测试](#验证测试)
6. [故障排查](#故障排查)

---

## 环境要求

### 软件要求

| 组件 | 版本 | 说明 |
|------|------|------|
| JDK | 8+ | Takin-web 运行环境 |
| Maven | 3.6+ | Takin-web 构建工具 |
| MySQL | 5.7+ | 数据库 |
| Redis | 5.0+ | 缓存 |
| Python | 3.8+ | PyLinkAgent 运行环境 |

### 网络要求

| 端口 | 服务 | 说明 |
|------|------|------|
| 9999 | Takin-web | Web 控制台端口 |
| 3306 | MySQL | 数据库端口 |
| 6379 | Redis | 缓存端口 |

---

## 数据库配置

### 步骤 1：创建数据库

```sql
CREATE DATABASE IF NOT EXISTS trodb 
DEFAULT CHARACTER SET utf8mb4 
DEFAULT COLLATE utf8mb4_unicode_ci;

USE trodb;
```

### 步骤 2：创建核心表

执行以下 SQL 脚本创建必要的表：

```sql
-- ============================================================
-- 1. 探针心跳数据表 (t_agent_report)
-- ============================================================
DROP TABLE IF EXISTS `t_agent_report`;
CREATE TABLE `t_agent_report` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `application_id` bigint(20) DEFAULT '0' COMMENT '应用 id',
  `application_name` varchar(64) DEFAULT '' COMMENT '应用名',
  `agent_id` varchar(600) NOT NULL COMMENT 'Agent 唯一标识',
  `ip_address` varchar(1024) DEFAULT '' COMMENT '节点 IP 地址',
  `progress_id` varchar(20) DEFAULT '' COMMENT '进程号',
  `agent_version` varchar(1024) DEFAULT '' COMMENT 'agent 版本号',
  `simulator_version` varchar(1024) DEFAULT NULL COMMENT 'simulator 版本',
  `cur_upgrade_batch` varchar(64) DEFAULT '0' COMMENT '升级批次',
  `status` tinyint(2) DEFAULT '0' COMMENT '节点状态 0:未知，1:启动中，2:升级待重启，3:运行中，4:异常，5:休眠，6:卸载',
  `agent_error_info` varchar(1024) DEFAULT NULL,
  `simulator_error_info` varchar(1024) DEFAULT NULL,
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP,
  `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `env_code` varchar(100) DEFAULT 'test' COMMENT '环境标识',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  `IS_DELETED` tinyint(4) NOT NULL DEFAULT '0' COMMENT '是否有效 0:有效;1:无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uni_applicationId_agentId_envCode_tenantId` (`application_id`,`agent_id`,`env_code`,`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='探针心跳数据';

-- ============================================================
-- 2. 应用管理表 (t_application_mnt)
-- ============================================================
DROP TABLE IF EXISTS `t_application_mnt`;
CREATE TABLE `t_application_mnt` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `APPLICATION_ID` bigint(19) NOT NULL COMMENT '应用 id',
  `APPLICATION_NAME` varchar(50) NOT NULL COMMENT '应用名称',
  `APPLICATION_DESC` varchar(200) DEFAULT NULL COMMENT '应用说明',
  `USE_YN` int(1) DEFAULT NULL COMMENT '是否可用 (0 表示启用，1 表示未启用)',
  `ACCESS_STATUS` int(2) NOT NULL DEFAULT '1' COMMENT '接入状态；0：正常；1:待配置；2:待检测;3:异常',
  `SWITCH_STATUS` varchar(255) NOT NULL DEFAULT 'OPENED' COMMENT 'OPENED:已开启',
  `CREATE_TIME` datetime DEFAULT CURRENT_TIMESTAMP,
  `UPDATE_TIME` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `env_code` varchar(20) DEFAULT 'test',
  `tenant_id` bigint(20) DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_app_name` (`APPLICATION_NAME`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用管理表';

-- ============================================================
-- 3. 应用数据源配置表 (t_application_ds_manage)
-- ============================================================
DROP TABLE IF EXISTS `t_application_ds_manage`;
CREATE TABLE `t_application_ds_manage` (
  `ID` bigint(20) NOT NULL AUTO_INCREMENT,
  `APPLICATION_ID` bigint(20) DEFAULT NULL,
  `APPLICATION_NAME` varchar(50) DEFAULT NULL,
  `DB_TYPE` tinyint(4) DEFAULT '0' COMMENT '存储类型 0:数据库 1:缓存',
  `DS_TYPE` tinyint(4) DEFAULT '0' COMMENT '方案类型 0:影子库 1:影子表',
  `CONFIG` longtext COMMENT '配置内容 (JSON 格式)',
  `PARSE_CONFIG` longtext COMMENT '解析后配置',
  `STATUS` tinyint(4) DEFAULT '0' COMMENT '状态 0:启用；1:禁用',
  `CREATE_TIME` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UPDATE_TIME` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `env_code` varchar(20) DEFAULT 'test',
  `tenant_id` bigint(20) DEFAULT '1',
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用数据源配置表';
```

### 步骤 3：插入测试数据

```sql
USE trodb;

-- 1. 插入测试应用
INSERT INTO `t_application_mnt`
(`APPLICATION_ID`, `APPLICATION_NAME`, `APPLICATION_DESC`, `USE_YN`, `ACCESS_STATUS`, `SWITCH_STATUS`, `env_code`, `tenant_id`)
VALUES
(1, 'demo-app', 'Demo Application', 0, 0, 'OPENED', 'test', 1);

-- 2. 插入影子库配置
INSERT INTO `t_application_ds_manage`
(`APPLICATION_ID`, `APPLICATION_NAME`, `DB_TYPE`, `DS_TYPE`, `CONFIG`, `PARSE_CONFIG`, `STATUS`, `env_code`, `tenant_id`)
VALUES
(1, 'demo-app', 0, 0, 
'{
  "datasourceMediator": {
    "dataSourceBusiness": "dataSourceBusiness",
    "dataSourcePerformanceTest": "dataSourcePerformanceTest"
  },
  "dataSources": [
    {
      "id": "dataSourceBusiness",
      "url": "jdbc:mysql://master-db:3306/demo_db",
      "username": "root",
      "password": "root123"
    },
    {
      "id": "dataSourcePerformanceTest",
      "url": "jdbc:mysql://shadow-db:3306/demo_db_shadow",
      "username": "root",
      "password": "root123"
    }
  ]
}',
'{}',
0, 'test', 1);
```

### 步骤 4：验证表和数据

```sql
-- 检查表是否存在
SHOW TABLES LIKE 't_%';

-- 检查应用数据
SELECT * FROM t_application_mnt;

-- 检查影子库配置
SELECT ID, APPLICATION_NAME, DS_TYPE, STATUS FROM t_application_ds_manage;
```

---

## Takin-web 部署

### 方式一：使用现有部署

如果有已部署的 Takin-web 服务，跳过此步骤，记录服务地址即可。

### 方式二：从源码编译部署

```bash
# 1. 进入项目目录
cd /d/soft/agent/takin-ee-web

# 2. 编译项目
mvn clean package -DskipTests

# 3. 查找编译后的 jar 包
find . -name "*.jar" | grep -v sources | grep -v javadoc
```

### 配置文件修改

编辑 `application.properties` 或使用环境变量覆盖：

```properties
# 数据库配置
spring.datasource.url=jdbc:mysql://localhost:3306/trodb?useUnicode=true&characterEncoding=UTF-8
spring.datasource.username=root
spring.datasource.password=your_password

# Redis 配置
spring.redis.host=localhost
spring.redis.port=6379

# 服务端口
server.port=9999
```

### 启动服务

```bash
# 启动 Takin-web
java -jar takin-web-ee-entrypoint-*.jar --server.port=9999

# 或使用 Spring Boot Maven 插件
mvn spring-boot:run -pl takin-web-ee-entrypoint
```

### 验证服务启动

```bash
# 检查端口
netstat -an | grep 9999

# 测试健康检查
curl http://localhost:9999/api/agent/heartbeat -X POST -H "Content-Type: application/json" -d '{}'
```

---

## PyLinkAgent 配置

### 步骤 1：安装依赖

```bash
cd D:/soft/agent/LinkAgent-main/PyLinkAgent
pip install -r requirements.txt
```

### 步骤 2：配置环境变量

创建 `.env` 文件：

```bash
# PyLinkAgent/.env

# Takin-web 地址
MANAGEMENT_URL=http://localhost:9999

# 应用配置
APP_NAME=demo-app
AGENT_ID=pylinkagent-001

# 节点配置
NODE_KEY=pylinkagent-node-1
REGISTER_NAME=zookeeper
```

### 步骤 3：运行验证脚本

```bash
# 测试与控制台通信
python scripts/test_takin_web_communication.py \
    --management-url http://localhost:9999 \
    --app-name demo-app \
    --agent-id pylinkagent-001
```

### 步骤 4：快速启动

```bash
python scripts/quickstart.py \
    --management-url http://localhost:9999 \
    --app-name demo-app \
    --agent-id pylinkagent-001
```

---

## 验证测试

### 测试 1：心跳上报验证

**目的**：验证 PyLinkAgent 能够成功上报心跳数据到 Takin-web

**步骤**：

1. 启动 PyLinkAgent
```bash
python scripts/quickstart.py
```

2. 在另一个终端执行 SQL 查询
```sql
-- 查看心跳记录
SELECT * FROM t_agent_report 
WHERE application_name = 'demo-app' 
ORDER BY gmt_update DESC 
LIMIT 10;
```

**预期结果**：
- `t_agent_report` 表中有记录插入
- `agent_id` 与配置一致
- `status` 字段为 3（运行中）
- `gmt_update` 字段持续更新

### 测试 2：影子库配置拉取验证

**目的**：验证 PyLinkAgent 能够成功拉取影子库配置

**步骤**：

1. 运行配置拉取测试
```bash
python -c "
from pylinkagent.controller.external_api import ExternalAPI

api = ExternalAPI(
    tro_web_url='http://localhost:9999',
    app_name='demo-app',
    agent_id='pylinkagent-001',
)
api.initialize()

configs = api.fetch_shadow_database_config()
print('配置拉取结果:')
for cfg in configs or []:
    print(cfg)
"
```

**预期结果**：
- 返回配置的影子库数据
- 包含主库 URL 和影子库 URL

### 测试 3：应用信息上报验证

**目的**：验证应用信息能够成功上报并入库

**步骤**：

1. 使用 Python 脚本上传应用
```bash
python -c "
from pylinkagent.controller.external_api import ExternalAPI

api = ExternalAPI(
    tro_web_url='http://localhost:9999',
    app_name='test-app-2',
    agent_id='pylinkagent-002',
)
api.initialize()

# 上传应用信息
success = api.upload_application_info({
    'applicationName': 'test-app-2',
    'applicationDesc': 'Test Application',
    'useYn': 0,
    'accessStatus': 0,
    'switchStatus': 'OPENED',
    'nodeNum': 1,
})
print(f'应用上传成功：{success}')
"
```

2. 检查数据库
```sql
SELECT * FROM t_application_mnt WHERE APPLICATION_NAME = 'test-app-2';
```

### 测试 4：压测流量路由验证

**目的**：验证带有压测流量标识的请求能够路由到影子库

**准备**：创建一个简单的 Python Web Demo

```python
# demo_app.py
from fastapi import FastAPI, Header
from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.config_fetcher import ConfigFetcher
import os
import time

app = FastAPI()

# 初始化 PyLinkAgent
api = ExternalAPI(
    tro_web_url="http://localhost:9999",
    app_name="demo-app",
    agent_id="pylinkagent-demo",
)
api.initialize()

fetcher = ConfigFetcher(api, interval=60)
fetcher.start()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/db/write")
async def db_write(x_pradar_trace: str = Header(None)):
    """
    模拟数据库写入操作
    x_pradar_trace: 压测流量标识头
    """
    # 获取当前影子库配置
    config = fetcher.get_config()
    
    is_pressure = False
    if x_pradar_trace and 'pressure' in x_pradar_trace.lower():
        is_pressure = True
    
    if is_pressure and config.shadow_database_configs:
        # 压测流量，写入影子库
        target_db = list(config.shadow_database_configs.values())[0].shadow_url
        return {"result": "写入影子库", "target": target_db}
    else:
        # 正常流量，写入主库
        target_db = list(config.shadow_database_configs.values())[0].url if config.shadow_database_configs else "master"
        return {"result": "写入主库", "target": target_db}
```

**测试命令**：

```bash
# 启动 Demo 应用
uvicorn demo_app:app --reload

# 测试正常流量
curl http://localhost:8000/db/write

# 测试压测流量
curl http://localhost:8000/db/write -H "X-Pradar-Trace: pressure-test"
```

---

## 故障排查

### 问题 1：连接被拒绝

**现象**：
```
[WinError 10061] 目标计算机主动拒绝连接
```

**解决**：
```bash
# 检查 Takin-web 是否运行
netstat -an | grep 9999

# 检查防火墙
telnet localhost 9999

# 启动 Takin-web
java -jar takin-web.jar
```

### 问题 2：心跳无记录

**现象**：心跳上报成功但数据库无记录

**检查**：
```sql
-- 检查应用是否存在
SELECT * FROM t_application_mnt WHERE APPLICATION_NAME = 'demo-app';

-- 检查表结构
DESC t_agent_report;
```

**解决**：
```sql
-- 插入缺失的应用
INSERT INTO t_application_mnt 
(APPLICATION_ID, APPLICATION_NAME, APPLICATION_DESC, USE_YN, ACCESS_STATUS, SWITCH_STATUS, env_code, tenant_id)
VALUES (1, 'demo-app', 'Demo', 0, 0, 'OPENED', 'test', 1);
```

### 问题 3：配置拉取返回空

**现象**：影子库配置返回空数组

**解决**：
```sql
-- 检查配置是否存在
SELECT ID, APPLICATION_NAME, DS_TYPE FROM t_application_ds_manage WHERE APPLICATION_NAME = 'demo-app';

-- 插入配置
INSERT INTO t_application_ds_manage ...;
```

### 问题 4：404 错误

**现象**：接口返回 404

**检查**：
```bash
# 确认接口路径
curl -v http://localhost:9999/api/agent/heartbeat

# 检查是否是正确的服务
# Takin-web: /api/agent/heartbeat
# agent-management: /open/agent/heartbeat
```

---

## 附录

### A. 完整验证脚本

```bash
#!/bin/bash
# verify_all.sh

echo "=== PyLinkAgent 端到端验证 ==="

# 1. 检查数据库
echo "1. 检查数据库连接..."
mysql -u root -p'trodb' -e "SELECT COUNT(*) FROM t_application_mnt;"

# 2. 检查 Takin-web
echo "2. 检查 Takin-web 服务..."
curl -s http://localhost:9999/api/agent/heartbeat -X POST -d '{}' > /dev/null && echo "OK" || echo "FAIL"

# 3. 运行 PyLinkAgent 验证
echo "3. 运行 PyLinkAgent 验证..."
python scripts/test_takin_web_communication.py

# 4. 检查心跳记录
echo "4. 检查心跳记录..."
mysql -u root -p'trodb' -e "SELECT agent_id, status, gmt_update FROM t_agent_report ORDER BY gmt_update DESC LIMIT 5;"

echo "=== 验证完成 ==="
```

### B. 接口速查表

| 接口 | 路径 | 方法 | 说明 |
|------|------|------|------|
| 心跳上报 | `/api/agent/heartbeat` | POST | 上报 Agent 心跳 |
| 应用上传 | `/api/application/center/app/info` | POST | 上传应用信息 |
| 影子库配置 | `/api/link/ds/configs/pull?appName=xxx` | GET | 拉取影子库配置 |
| 命令拉取 | `/api/agent/application/node/probe/operate` | GET | 拉取命令 |
| 命令结果上报 | `/api/agent/application/node/probe/operateResult` | POST | 上报命令结果 |

### C. 数据库表关系

```
t_application_mnt (应用信息)
    ├── t_agent_report (心跳记录)
    └── t_application_ds_manage (数据源配置)
```

---

**文档版本**: 1.0.0  
**创建日期**: 2026-04-11  
**适用版本**: PyLinkAgent 2.0.0+, Takin-web 5.x+
