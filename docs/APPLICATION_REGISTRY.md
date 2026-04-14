# PyLinkAgent 应用自动注册功能

> **版本**: v2.0.0  
> **更新日期**: 2026-04-14  
> **P0 任务完成状态**: ✅ 已完成

---

## 一、概述

应用自动注册功能实现了 PyLinkAgent 在启动时自动向 Takin-web 控制台注册应用，无需手动在控制台创建应用。该功能参考 Java LinkAgent 的 `HttpApplicationUploader` 实现。

### 1.1 核心功能

| 功能 | 说明 | 状态 |
|------|------|------|
| **应用信息上传** | 向控制台提交应用基本信息 | ✅ |
| **自动生成应用信息** | 从环境变量自动生成完整应用信息 | ✅ |
| **租户信息支持** | 支持 tenant_id, env_code, user_id | ✅ |
| **集群信息支持** | 支持 cluster_name 配置 | ✅ |
| **状态上报** | 应用接入状态上报 | ✅ |
| **配置错误上报** | 配置失败时上报错误信息 | ✅ |
| **应用信息同步** | 定期同步应用节点数 | ⏳ |

---

## 二、架构设计

### 2.1 模块结构

```
pylinkagent/controller/
├── application_register.py    # 应用注册核心模块
│   ├── ApplicationInfo        # 应用信息数据类
│   ├── ApplicationRegistrator # 应用注册器
│   └── ApplicationStatusReporter # 状态上报器
├── external_api.py            # 外部 API (包含上传接口)
└── __init__.py                # 模块导出
```

### 2.2 类关系

```
PyLinkAgentBootstrapper
    │
    ├─ ExternalAPI
    │   └─ upload_application_info()
    │
    └─ ApplicationRegistrator
        ├─ register() → 调用 ExternalAPI
        ├─ _generate_app_info() → 生成 ApplicationInfo
        └─ is_registered() → 检查注册状态
```

### 2.3 注册流程

```
Agent 启动
    │
    ├─ 1. 初始化 ExternalAPI
    │   └─ 配置控制台地址、应用名称、Agent ID
    │
    ├─ 2. 创建 ApplicationRegistrator
    │   └─ 传入 ExternalAPI 实例
    │
    ├─ 3. 生成应用信息
    │   ├─ 从环境变量读取配置
    │   ├─ 自动生成主机名、IP 地址
    │   └─ 填充默认值
    │
    ├─ 4. 上传应用信息
    │   └─ POST /api/application/center/app/info
    │
    └─ 5. 记录注册状态
        └─ 成功 → _is_registered = True
```

---

## 三、配置说明

### 3.1 环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `MANAGEMENT_URL` | 控制台 Web 地址 | `http://localhost:9999` | 是 |
| `APP_NAME` | 应用名称 | `default-app` | 是 |
| `AGENT_ID` | Agent 标识 | `pylinkagent-{pid}` | 否 |
| `AUTO_REGISTER_APP` | 是否启用自动注册 | `true` | 否 |
| `CLUSTER_NAME` | 集群名称 | `default` | 否 |
| `SIMULATOR_TENANT_ID` | 租户 ID | `1` | 否 |
| `SIMULATOR_ENV_CODE` | 环境代码 | `test` | 否 |
| `SIMULATOR_USER_ID` | 用户 ID | `` | 否 |

### 3.2 应用信息格式

```python
{
    "applicationName": "my-app",           # 应用名称
    "applicationDesc": "Application: ...", # 应用描述
    "useYn": 0,                            # 0:启用，1:禁用
    "accessStatus": 0,                     # 0:正常，1:待配置，2:待检测，3:异常
    "switchStatus": "OPENED",              # OPENED/CLOSED
    "nodeNum": 1,                          # 节点数量
    "agentVersion": "2.0.0",               # Agent 版本
    "pradarVersion": "2.0.0",              # Pradar 版本
    "clusterName": "default",              # 集群名称
    "tenantId": "1",                       # 租户 ID
    "envCode": "test",                     # 环境代码
    "userId": "",                          # 用户 ID
}
```

---

## 四、使用指南

### 4.1 快速启动（自动注册）

```bash
# 1. 设置环境变量
export MANAGEMENT_URL=http://localhost:9999
export APP_NAME=my-app
export AGENT_ID=agent-001

# 2. 启动 Agent
python scripts/quickstart_agent.py
```

启动日志：
```
============================================================
PyLinkAgent 启动中...
============================================================
初始化 ExternalAPI:
  控制台地址：http://localhost:9999
  应用名称：my-app
  Agent ID: agent-001
注册应用...
  应用注册成功
============================================================
PyLinkAgent 启动完成
============================================================
```

### 4.2 禁用自动注册

```bash
# 设置环境变量禁用自动注册
export AUTO_REGISTER_APP=false

# 启动 Agent
python scripts/quickstart_agent.py
```

启动日志：
```
初始化 ExternalAPI:
  ...
应用自动注册已禁用 (AUTO_REGISTER_APP=false)
```

### 4.3 作为库使用

```python
from pylinkagent.controller import (
    ExternalAPI,
    ApplicationRegistrator,
    ApplicationInfo,
)

# 创建 ExternalAPI
api = ExternalAPI(
    tro_web_url="http://localhost:9999",
    app_name="my-app",
    agent_id="agent-001",
)
api.initialize()

# 创建注册器
registrator = ApplicationRegistrator(api)

# 注册应用
if registrator.register():
    print("应用注册成功")
else:
    print("应用注册失败")

# 检查注册状态
if registrator.is_registered():
    print("应用已注册")
```

### 4.4 自定义应用信息

```python
from pylinkagent.controller import ApplicationRegistrator, ApplicationInfo

registrator = ApplicationRegistrator(api)

# 创建自定义应用信息
app_info = ApplicationInfo(
    application_name="my-app",
    application_desc="My Custom Application",
    use_yn=0,
    access_status=0,
    switch_status="OPENED",
    node_num=1,
    agent_version="2.0.0",
    pradar_version="2.0.0",
    cluster_name="production",
    tenant_id="tenant-123",
    env_code="prod",
    user_id="user-001",
)

# 注册
registrator.register(app_info)
```

---

## 五、状态上报

### 5.1 上报应用接入状态

```python
from pylinkagent.controller import ApplicationStatusReporter

reporter = ApplicationStatusReporter(api)

# 上报正常状态
reporter.report_access_status(status=0)

# 上报错误状态
reporter.report_access_status(
    status=3,
    error_info={"configType": "shadow_db", "errorMsg": "连接失败"}
)
```

### 5.2 上报配置错误

```python
# 上报影子库配置错误
reporter.report_config_error(
    config_type="shadow_db",
    error_msg="JDBC 连接超时"
)

# 上报配置成功
reporter.report_config_success(config_type="shadow_db")
```

### 5.3 清除错误信息

```python
reporter.clear_errors()
```

---

## 六、测试验证

### 6.1 运行单元测试

```bash
cd PyLinkAgent
python tests/test_application_register.py
```

### 6.2 测试项目

| 测试项 | 说明 | 状态 |
|--------|------|------|
| ApplicationInfo 数据类 | 创建、to_dict 转换 | ✅ |
| ApplicationRegistrator 结构 | 方法存在性检查 | ✅ |
| ApplicationStatusReporter 结构 | 方法存在性检查 | ✅ |
| 应用信息生成 | 自动生成完整应用信息 | ✅ |
| 上传应用信息 | 实际调用控制台接口 | ⏳ (需控制台) |

---

## 七、控制台对接

### 7.1 接口定义

**接口**: `POST /api/application/center/app/info`

**请求体**:
```json
{
  "applicationName": "my-app",
  "applicationDesc": "Application Description",
  "useYn": 0,
  "accessStatus": 0,
  "switchStatus": "OPENED",
  "nodeNum": 1,
  "agentVersion": "2.0.0",
  "pradarVersion": "2.0.0",
  "clusterName": "default",
  "tenantId": "1",
  "envCode": "test",
  "userId": ""
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "applicationId": "123456",
    "applicationName": "my-app"
  }
}
```

### 7.2 数据库表

应用信息存储在 Takin-web 的 `t_application_mnt` 表中：

```sql
-- 查看应用
SELECT * FROM t_application_mnt WHERE APPLICATION_NAME = 'my-app';

-- 手动插入应用 (如果自动注册失败)
INSERT INTO t_application_mnt (
    APPLICATION_NAME, CLUSTER_NAME, USE_YN, ACCESS_STATUS,
    SWITCH_STATUS, NODE_NUM, AGENT_VERSION, PRADAR_VERSION,
    TENANT_ID, ENV_CODE, USER_ID
) VALUES (
    'my-app', 'default', 0, 0, 'OPENED', 1, '2.0.0', '2.0.0',
    '1', 'test', ''
);
```

---

## 八、故障排查

### 8.1 注册失败

**问题**: 应用注册返回失败

**排查步骤**:
```bash
# 1. 检查控制台是否运行
curl http://localhost:9999

# 2. 检查应用名称是否重复
# 在控制台查看应用列表

# 3. 查看日志
tail -f logs/pylinkagent.log
```

### 8.2 控制台不可用

**问题**: 控制台未启动或网络不可达

**解决方案**:
1. 启动 Takin-web 控制台
2. 检查 MANAGEMENT_URL 配置
3. 检查防火墙设置

### 8.3 应用已存在

**问题**: 应用已在数据库中存在

**解决方案**:
- 控制台的响应可能返回 success=false 但应用实际已存在
- 这是正常行为，不影响后续功能

---

## 九、与 Java LinkAgent 对比

| 功能 | Java LinkAgent | PyLinkAgent | 状态 |
|------|----------------|-------------|------|
| 实现类 | HttpApplicationUploader | ApplicationRegistrator | ✅ 对等 |
| 数据类 | ApplicationInfoDTO | ApplicationInfo | ✅ 对等 |
| 接口路径 | /api/application/center/app/info | 同上 | ✅ 对等 |
| 自动生成 | 从配置文件/环境变量 | 从环境变量 | ✅ 对等 |
| 租户支持 | tenantId, envCode, userId | 同上 | ✅ 对等 |
| 集群支持 | clusterName | 同上 | ✅ 对等 |
| 状态上报 | uploadAccessStatus | upload_access_status | ✅ 对等 |

---

## 十、下一步

### 10.1 待实现功能

- [ ] 应用信息同步（定期更新 node_num）
- [ ] 从控制台读取应用 ID 并缓存
- [ ] 支持应用描述模板
- [ ] 支持自定义脚本路径配置

### 10.2 相关功能

- [P0] ✅ ZooKeeper 集成
- [P0] ✅ 应用自动注册
- [P1] ⏳ 客户端路径注册
- [P1] ⏳ 完整配置拉取 (Redis/ES/Kafka)

---

**文档完成日期**: 2026-04-14  
**版本**: v1.0
