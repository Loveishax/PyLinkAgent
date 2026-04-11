# PyLinkAgent - 部署与验证指南

## 概述

本文档说明如何部署 PyLinkAgent 并与 Takin-web 进行集成验证。

## 前置要求

### 1. 环境要求

- **Python**: 3.8+
- **MySQL**: 5.7+ (Takin-web 后端数据库)
- **Takin-web**: 运行中的控制台服务 (端口 9999)

### 2. Python 依赖

```bash
cd PyLinkAgent
pip install -r requirements.txt
```

核心依赖：
- `httpx` (优先) 或 `requests` - HTTP 客户端
- `python-dotenv` - 环境变量管理 (可选)

### 3. 数据库准备

执行数据库表创建脚本：

```bash
# 1. 登录 MySQL
mysql -u root -p

# 2. 选择 Takin-web 使用的数据库
USE takin_web;

# 3. 执行表创建脚本
source D:/soft/agent/LinkAgent-main/PyLinkAgent/database/pylinkagent_tables.sql
```

或者使用 MySQL 客户端工具导入 SQL 文件。

### 4. 验证数据库表

确认以下表已创建：

```sql
SHOW TABLES LIKE 't_%';

-- 应显示:
-- t_agent_report           (探针心跳数据)
-- t_application_mnt        (应用管理表)
-- t_application_ds_manage  (应用数据源配置)
-- t_shadow_table_datasource (影子表数据源)
-- t_shadow_job_config      (影子 Job 配置)
-- t_shadow_mq_consumer     (影子 MQ 消费者)
-- t_application_node_probe (探针操作记录)
```

## 部署步骤

### 步骤 1: 配置环境变量

创建 `.env` 文件（可选）：

```bash
# PyLinkAgent/.env

# Takin-web 地址
MANAGEMENT_URL=http://localhost:9999

# 应用配置
APP_NAME=test-app
AGENT_ID=pylinkagent-001

# 网络配置
NODE_KEY=pylinkagent-node-1
REGISTER_NAME=zookeeper  # 或 kafka
```

### 步骤 2: 在 Takin-web 中注册应用

**方式一：通过 SQL 直接插入**

```sql
INSERT INTO `t_application_mnt`
(`APPLICATION_ID`, `APPLICATION_NAME`, `APPLICATION_DESC`, `USE_YN`, `ACCESS_STATUS`, `SWITCH_STATUS`, `CREATE_TIME`, `UPDATE_TIME`, `env_code`, `tenant_id`)
VALUES
(1, 'test-app', '测试应用', 0, 0, 'OPENED', NOW(), NOW(), 'test', 1);
```

**方式二：通过 PyLinkAgent 上传**

运行测试脚本时会自动上传应用信息。

### 步骤 3: 配置影子库（可选）

在 Takin-web 前端配置影子库，或通过 SQL 插入：

```sql
INSERT INTO `t_application_ds_manage`
(`APPLICATION_ID`, `APPLICATION_NAME`, `DB_TYPE`, `DS_TYPE`, `CONFIG`, `PARSE_CONFIG`, `STATUS`, `CREATE_TIME`, `UPDATE_TIME`, `env_code`, `tenant_id`)
VALUES
(1, 'test-app', 0, 0,
'{
  "datasourceMediator": {
    "dataSourceBusiness": "dataSourceBusiness",
    "dataSourcePerformanceTest": "dataSourcePerformanceTest"
  },
  "dataSources": [
    {
      "id": "dataSourceBusiness",
      "url": "jdbc:mysql://master-db:3306/test_db",
      "username": "root",
      "password": "password123"
    },
    {
      "id": "dataSourcePerformanceTest",
      "url": "jdbc:mysql://shadow-db:3306/test_db_shadow",
      "username": "root_shadow",
      "password": "shadow_password123"
    }
  ]
}',
'{}',
0, NOW(), NOW(), 'test', 1);
```

### 步骤 4: 启动 Takin-web 服务

确保 Takin-web 服务已启动：

```bash
# 方式一：使用 Docker (如果有镜像)
docker run -d --name takin-web -p 9999:9999 takin-web:latest

# 方式二：启动 Java 服务
cd takin-web
mvn spring-boot:run
```

验证服务可访问：

```bash
curl http://localhost:9999/api/agent/heartbeat -X POST -H "Content-Type: application/json" -d '{}'
```

### 步骤 5: 运行验证脚本

```bash
cd PyLinkAgent

# 方式一：使用默认配置
python scripts/test_takin_web_communication.py

# 方式二：指定配置
python scripts/test_takin_web_communication.py \
    --management-url http://192.168.1.100:9999 \
    --app-name my-app \
    --agent-id agent-001
```

### 步骤 6: 验证数据库记录

心跳成功后，检查数据库中的心跳记录：

```sql
-- 查看心跳记录
SELECT * FROM t_agent_report 
WHERE application_name = 'test-app' 
ORDER BY gmt_update DESC 
LIMIT 10;

-- 查看应用信息
SELECT * FROM t_application_mnt 
WHERE APPLICATION_NAME = 'test-app';
```

## 运行 PyLinkAgent

### 方式一：作为独立进程运行

```bash
python -m pylinkagent
```

### 方式二：集成到现有项目

```python
from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.config_fetcher import ConfigFetcher
import os
import time

# 1. 初始化
external_api = ExternalAPI(
    tro_web_url="http://localhost:9999",
    app_name="my-app",
    agent_id="agent-001",
)
external_api.initialize()

# 2. 启动配置拉取器
fetcher = ConfigFetcher(external_api, interval=60)
fetcher.start()

# 3. 发送心跳
heart_request = HeartRequest(
    project_name="my-app",
    agent_id="agent-001",
    ip_address="192.168.1.100",
    progress_id=str(os.getpid()),
)
commands = external_api.send_heartbeat(heart_request)

# 4. 执行命令
for cmd in commands:
    if cmd.id > 0:
        print(f"执行命令：{cmd.id}")
        # ... 执行命令逻辑 ...
        external_api.report_command_result(cmd.id, True)

# 5. 保持运行
try:
    while True:
        time.sleep(10)
except KeyboardInterrupt:
    fetcher.stop()
    external_api.shutdown()
```

### 方式三：作为库使用

```python
# 仅使用影子库配置拉取
from pylinkagent.controller.external_api import ExternalAPI

api = ExternalAPI(
    tro_web_url="http://takin-web:9999",
    app_name="my-app",
    agent_id="agent-001",
)
api.initialize()

configs = api.fetch_shadow_database_config()
for cfg in configs:
    print(f"数据源：{cfg['dataSourceName']}")
    print(f"  主库：{cfg['url']}")
    print(f"  影子库：{cfg['shadowUrl']}")
```

## 验证检查清单

### 基础验证

- [ ] Takin-web 服务可访问
- [ ] 数据库表已创建
- [ ] 应用已注册（`t_application_mnt` 有记录）
- [ ] ExternalAPI 初始化成功

### 心跳验证

- [ ] 心跳接口返回 HTTP 200
- [ ] `t_agent_report` 表有心跳记录
- [ ] 心跳记录包含正确的 `agent_id` 和 `application_name`
- [ ] 持续心跳稳定（无失败）

### 配置拉取验证

- [ ] 影子库配置接口可访问
- [ ] 配置数据解析正确
- [ ] ConfigFetcher 定时拉取正常
- [ ] 配置变更回调触发

### 命令交互验证

- [ ] 命令拉取接口可访问
- [ ] 命令结果上报成功
- [ ] `t_application_node_probe` 有操作记录

## 故障排查

### 问题 1: 连接被拒绝

**现象**: `[WinError 10061] 目标计算机主动拒绝连接`

**原因**: Takin-web 服务未启动或端口不对

**解决**:
```bash
# 检查服务状态
netstat -an | grep 9999

# 启动 Takin-web
# ...

# 检查防火墙
telnet localhost 9999
```

### 问题 2: 心跳返回 404

**现象**: `HTTP 404 Not Found`

**原因**: 接口路径错误或使用了错误的服务

**解决**:
- 确认 URL 是 `http://<host>:9999` (Takin-web 端口)
- 确认接口路径是 `/api/agent/heartbeat` (不是 `/open/agent/heartbeat`)

### 问题 3: 配置拉取返回空

**现象**: 影子库配置返回空数组

**原因**: Takin-web 未配置影子库

**解决**:
- 在 Takin-web 前端配置影子库
- 或直接在 `t_application_ds_manage` 表插入配置

### 问题 4: 数据库无心跳记录

**现象**: 心跳接口返回成功，但数据库无记录

**原因**: 
- 应用未预先注册
- 租户 ID 或环境代码不匹配

**解决**:
```sql
-- 检查应用是否存在
SELECT * FROM t_application_mnt WHERE APPLICATION_NAME = 'test-app';

-- 如果不存在，插入应用
INSERT INTO t_application_mnt ...;
```

## 日志配置

### 调试模式

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 日志文件

```python
import logging

handler = logging.FileHandler('pylinkagent.log')
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger('pylinkagent')
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

## 性能调优

### HTTP 连接池

使用 httpx 时自动启用连接池：

```python
external_api = ExternalAPI(
    tro_web_url="http://takin-web:9999",
    app_name="my-app",
    agent_id="agent-001",
    timeout=30,  # 超时时间
)
```

### 配置拉取间隔

```python
# 生产环境建议 60-300 秒
fetcher = ConfigFetcher(external_api, interval=120)
```

### 心跳频率

```python
# 建议 10-30 秒发送一次心跳
while True:
    external_api.send_heartbeat(heart_request)
    time.sleep(15)  # 15 秒
```

## 安全注意事项

1. **API 密钥**: 生产环境应配置 `api_key`
2. **HTTPS**: 生产环境应使用 HTTPS
3. **密码脱敏**: 日志中应隐藏密码字段
4. **网络隔离**: 确保 PyLinkAgent 和 Takin-web 在同一网络

## 常见问题 (FAQ)

### Q: PyLinkAgent 和 Java Agent 能同时运行吗？

A: 可以。两者使用相同的 API 接口，互不影响。

### Q: 如何查看详细的 HTTP 请求日志？

A: 启用 httpx 或 requests 的 DEBUG 日志：
```python
logging.getLogger('httpx').setLevel(logging.DEBUG)
logging.getLogger('urllib3').setLevel(logging.DEBUG)
```

### Q: 影子库配置的更新频率是多少？

A: ConfigFetcher 默认每 60 秒拉取一次，可通过 `interval` 参数调整。

### Q: 如何验证影子库配置生效？

A: 检查 ConfigFetcher 的配置输出，并验证数据源路由逻辑。

## 附录

### API 端点完整列表

| 功能 | 端点 | 方法 |
|------|------|------|
| 心跳上报 | `/api/agent/heartbeat` | POST |
| 命令拉取 | `/api/agent/application/node/probe/operate` | GET |
| 命令结果上报 | `/api/agent/application/node/probe/operateResult` | POST |
| 影子库配置 | `/api/link/ds/configs/pull` | GET |
| 远程调用配置 | `/api/remote/call/configs/pull` | GET |
| 影子 Job 配置 | `/api/shadow/job/queryByAppName` | GET |
| 影子 MQ 配置 | `/api/agent/configs/shadow/consumer` | GET |
| 应用信息上传 | `/api/application/center/app/info` | POST |
| 接入状态上报 | `/api/application/agent/access/status` | POST |

### 数据库表关系

```
t_application_mnt (应用信息)
    └── t_agent_report (心跳记录)
    └── t_application_ds_manage (数据源配置)
        └── t_shadow_table_datasource (影子表数据源)
    └── t_application_node_probe (操作记录)
    └── t_shadow_job_config (Job 配置)
    └── t_shadow_mq_consumer (MQ 消费者配置)
```

---

**文档版本**: 1.0.0  
**更新日期**: 2026-04-11  
**适用版本**: PyLinkAgent 2.0.0+
