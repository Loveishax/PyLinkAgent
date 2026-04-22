# PyLinkAgent

[![LICENSE](https://img.shields.io/github/license/pingcap/tidb.svg)](https://github.com/pingcap/tidb/blob/master/LICENSE)
[![Language](https://img.shields.io/badge/Language-Python-blue.svg)](https://www.python.org/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

PyLinkAgent 是一个基于 Python 的链路追踪探针 Agent，与 Takin-web / takin-ee-web 控制台对接，提供应用性能监控和压测流量标识能力。

## 核心特性

### Takin-web 对接功能

- **心跳上报**: 定期向 Takin-web 上报 Agent 状态
- **配置拉取**: 动态拉取影子库、影子 Job 等配置
- **命令接收**: 接收并执行控制台下发的命令（安装/升级/卸载）
- **流量标识**: 识别压测流量并路由到影子库
- **影子路由**: 零侵入组件拦截 (MySQL/Redis/ES/Kafka/HTTP)
- **多租户支持**: 支持 tenant_id 和 env_code 隔离

### 原始插桩功能

- **零代码侵入**：无需修改任何业务代码，通过环境变量或包装器启动即可
- **数据采集**：支持 Trace、Metric、自定义埋点
- **函数控制**：支持流量染色、Mock、Chaos 注入、压测标、限流等
- **模块化架构**：可插拔的模块设计，支持快速扩展新框架
- **异步支持**：完整支持 asyncio 异步场景
- **主流框架支持**：FastAPI、Flask、Django、requests、SQLAlchemy、Redis 等

## 快速开始

### 1. 安装依赖

```bash
cd PyLinkAgent
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# Takin-web 地址
export MANAGEMENT_URL=http://localhost:9999

# 应用配置
export APP_NAME=my-app
export AGENT_ID=agent-001
```

### 3. 运行验证脚本

```bash
# 验证与控制台通信
python scripts/test_takin_web_communication.py

# 快速启动
python scripts/quickstart.py
```

### 4. 作为库使用

```python
from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.config_fetcher import ConfigFetcher
import os
import time

# 初始化
api = ExternalAPI(
    tro_web_url="http://localhost:9999",
    app_name="my-app",
    agent_id="agent-001",
)
api.initialize()

# 启动配置拉取
fetcher = ConfigFetcher(api, interval=60)
fetcher.start()

# 发送心跳
heart_request = HeartRequest(
    project_name="my-app",
    agent_id="agent-001",
    ip_address="192.168.1.100",
    progress_id=str(os.getpid()),
)
commands = api.send_heartbeat(heart_request)

# 处理命令
for cmd in commands:
    if cmd.id > 0:
        print(f"执行命令：{cmd.id}")
        api.report_command_result(cmd.id, True)

# 保持运行
try:
    while True:
        time.sleep(15)
except KeyboardInterrupt:
    fetcher.stop()
    api.shutdown()
```

## 快速开始 (原始插桩功能)

### 方式一：环境变量注入（推荐）

```bash
# 1. 安装
pip install pylinkagent

# 2. 设置环境变量
export PYLINKAGENT_ENABLED=true
export PYLINKAGENT_PLATFORM_URL=http://localhost:8080

# 3. 启动应用
python app.py
```

### 方式二：包装器启动

```bash
pylinkagent-run python app.py
```

### 方式三：代码中导入

```python
# 在 app.py 的第一行导入
import pylinkagent
pylinkagent.bootstrap()

# 然后是你的应用代码
from fastapi import FastAPI
app = FastAPI()
```

## 项目结构

```
PyLinkAgent/
├── pylinkagent/                 # 核心包
│   ├── controller/              # 控制器
│   │   ├── external_api.py      # 外部 API (与控制台通信)
│   │   └── config_fetcher.py    # 配置拉取器
│   ├── shadow/                  # 影子路由
│   │   ├── config_center.py     # 配置中心 (存储/热更新)
│   │   ├── router.py            # 路由决策引擎
│   │   ├── sql_rewriter.py      # SQL 表名重写
│   │   ├── mysql_interceptor.py # MySQL 拦截
│   │   ├── redis_interceptor.py # Redis 拦截
│   │   ├── es_interceptor.py    # ES 拦截
│   │   ├── kafka_interceptor.py # Kafka 拦截
│   │   └── http_interceptor.py  # HTTP 拦截
│   ├── pradar/                  # 链路追踪
│   ├── zookeeper/               # ZK 集成
├── scripts/                     # 脚本
│   ├── verify_shadow_routing.py      # 影子路由验证
│   └── comprehensive_verification.py # 综合验证
├── database/                    # 数据库脚本
│   └── pylinkagent_tables.sql   # 表定义
├── docs/                        # 文档
│   ├── SHADOW_ROUTING_GUIDE.md     # 影子路由指南
│   ├── COMPREHENSIVE_VERIFICATION_GUIDE.md  # 综合验证指南
│   ├── ZOOKEEPER_INTEGRATION.md    # ZK 集成
│   └── architecture.md             # 架构设计
├── requirements.txt             # 依赖
└── README.md                    # 本文档
```

### 原始插桩模块

```
├── pylinkagent/                # 核心包
│   ├── core/                   # 核心引擎
│   ├── patcher/                # 插桩引擎
│   ├── lifecycle/              # 生命周期管理
│   └── utils/                  # 工具函数
├── instrument_simulator/       # 探针框架
├── instrument_modules/         # 插桩模块
│   ├── requests_module/        # requests 插桩
│   ├── fastapi_module/         # FastAPI 插桩
│   └── ...
└── config/                     # 配置文件
```

## 框架支持

| 类型 | 名称 | 状态 |
|------|------|------|
| HTTP 客户端 | requests | ✅ |
| HTTP 客户端 | httpx | ✅ |
| Web 框架 | FastAPI | ✅ |

> ✅ 已实现 | ⏳ 计划中

## 开发与构建

```bash
# 安装依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
pytest tests/ -v
```

## 核心接口

### ExternalAPI

与控制台 (Takin-web) 通信的核心接口：

| 方法 | 功能 | 接口路径 |
|------|------|----------|
| `send_heartbeat()` | 心跳上报 | `/api/agent/heartbeat` |
| `fetch_shadow_database_config()` | 拉取影子库配置 | `/api/link/ds/configs/pull` |
| `get_latest_command()` | 拉取命令 | `/api/agent/application/node/probe/operate` |
| `report_command_result()` | 上报命令结果 | `/api/agent/application/node/probe/operateResult` |
| `upload_application_info()` | 上传应用信息 | `/api/application/center/app/info` |
| `fetch_shadow_job_config()` | 拉取影子 Job 配置 | `/api/shadow/job/queryByAppName` |

### ConfigFetcher

定时拉取配置的器：

```python
fetcher = ConfigFetcher(api, interval=60)
fetcher.start()

# 注册配置变更回调
fetcher.on_config_change(lambda key, old, new: print(f"{key} 变更"))

# 获取当前配置
config = fetcher.get_config()
for name, cfg in config.shadow_database_configs.items():
    print(f"{name}: {cfg.url} -> {cfg.shadow_url}")
```

## 配置项

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `MANAGEMENT_URL` | Takin-web 地址 | `http://localhost:9999` |
| `APP_NAME` | 应用名称 | `test-app` |
| `AGENT_ID` | Agent ID | `pylinkagent-001` |
| `NODE_KEY` | 节点标识 | `pylinkagent-<pid>` |
| `REGISTER_NAME` | 注册中心 (zookeeper/kafka) | `zookeeper` |

## 数据库表

PyLinkAgent 使用以下数据库表（由 Takin-web 管理）：

| 表名 | 说明 |
|------|------|
| `t_agent_report` | 探针心跳数据 |
| `t_application_mnt` | 应用管理 |
| `t_application_ds_manage` | 数据源配置 |
| `t_shadow_table_datasource` | 影子表数据源 |
| `t_shadow_job_config` | 影子 Job 配置 |
| `t_shadow_mq_consumer` | 影子 MQ 消费者 |
| `t_application_node_probe` | 探针操作记录 |

创建表：
```bash
mysql -u root -p takin_web < database/pylinkagent_tables.sql
```

## 文档

- [影子路由指南 (docs/SHADOW_ROUTING_GUIDE.md)](docs/SHADOW_ROUTING_GUIDE.md) - 影子路由完整流程
- [综合验证指南 (docs/COMPREHENSIVE_VERIFICATION_GUIDE.md)](docs/COMPREHENSIVE_VERIFICATION_GUIDE.md) - 验证脚本使用说明
- [架构设计 (docs/architecture.md)](docs/architecture.md) - 架构与插桩设计

## 故障排查

### 连接被拒绝

```bash
# 检查 Takin-web 是否运行
curl http://localhost:9999

# 检查端口
netstat -an | grep 9999
```

### 配置拉取返回空

- 确认应用在 Takin-web 中已注册
- 确认影子库配置已创建

### 心跳无记录

```sql
-- 检查应用是否存在
SELECT * FROM t_application_mnt WHERE APPLICATION_NAME = 'my-app';

-- 查看心跳记录
SELECT * FROM t_agent_report ORDER BY gmt_update DESC LIMIT 10;
```

## 版本历史

### 2.0.0 (2026-04-11) - 重构版本

- 重构与控制台通信接口，对接 Takin-web
- 新增影子库配置拉取
- 重写 ConfigFetcher
- 完善验证工具和文档

### 1.0.0 (早期版本)

- 基础探针功能
- 原始插桩模块

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

Apache 2.0 License

## 社区

- 邮件列表：pylinkagent@googlegroups.com
- GitHub Discussions: https://github.com/your-org/PyLinkAgent/discussions
