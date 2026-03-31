# PyLinkAgent

[![LICENSE](https://img.shields.io/github/license/pingcap/tidb.svg)](https://github.com/pingcap/tidb/blob/master/LICENSE)
[![Language](https://img.shields.io/badge/Language-Python-blue.svg)](https://www.python.org/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

PyLinkAgent 是一个基于 Python 的运行时探针，设计灵感来源于 LinkAgent (Java)。它通过运行时插桩技术（无需修改任何业务应用代码）实现对 Python 应用的**数据采集**和**函数控制**。

## 核心特性

- **零代码侵入**：无需修改任何业务代码，通过环境变量或包装器启动即可
- **数据采集**：支持 Trace、Metric、自定义埋点
- **函数控制**：支持流量染色、Mock、Chaos 注入、压测标、限流等
- **模块化架构**：可插拔的模块设计，支持快速扩展新框架
- **异步支持**：完整支持 asyncio 异步场景
- **主流框架支持**：FastAPI、Flask、Django、requests、SQLAlchemy、Redis 等

## 快速开始

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
├── pylinkagent/                # 核心包
│   ├── core/                   # 核心引擎
│   ├── patcher/                # 插桩引擎
│   ├── lifecycle/              # 生命周期管理
│   └── utils/                  # 工具函数
├── simulator_agent/            # 控制面模块
├── instrument_simulator/       # 探针框架
├── instrument_modules/         # 插桩模块
│   ├── requests_module/        # requests 插桩
│   ├── fastapi_module/         # FastAPI 插桩
│   └── ...
├── config/                     # 配置文件
├── tests/                      # 测试
└── docs/                       # 文档
```

## 支持的框架和库

| 类型 | 名称 | 状态 |
|------|------|------|
| HTTP 客户端 | requests | ✅ |
| HTTP 客户端 | httpx | ✅ |
| HTTP 客户端 | aiohttp | ⏳ |
| Web 框架 | FastAPI | ✅ |
| Web 框架 | Flask | ⏳ |
| Web 框架 | Django | ⏳ |
| 数据库 | SQLAlchemy | ⏳ |
| 缓存 | Redis | ⏳ |
| 消息队列 | Kafka | ⏳ |
| 消息队列 | RabbitMQ | ⏳ |

> ✅ 已实现 | ⏳ 计划中

## 配置示例

```yaml
# pylinkagent.yaml
agent_id: "my-app-001"
app_name: "my-fastapi-app"
enabled: true
log_level: "INFO"

platform:
  url: "http://localhost:8080"
  api_key: "your-api-key"

sampler:
  trace_sample_rate: 0.1  # 10% 采样

enabled_modules:
  - requests
  - fastapi
```

## 开发与构建

```bash
# 克隆项目
git clone https://github.com/your-org/PyLinkAgent.git
cd PyLinkAgent

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# 安装开发依赖
pip install -r requirements-dev.txt

# 安装项目（可编辑模式）
pip install -e .

# 运行测试
pytest tests/ -v

# 构建
make build
```

## 命令行工具

```bash
# 查看探针状态
pylinkagent-cli status

# 模块管理
pylinkagent-cli modules list
pylinkagent-cli modules reload requests

# 配置管理
pylinkagent-cli config show

# 交互式模式
pylinkagent-cli shell
```

## 文档

- [架构设计文档](docs/architecture.md)
- [快速开始](docs/quickstart.md)
- [构建指南](docs/howtobuild.md)
- [模块开发指南](docs/module-development.md)
- [配置说明](docs/configuration.md)
- [FAQ](docs/faq.md)

## 性能影响

在典型 Web 应用场景下：
- 无插桩模式：零开销
- 启用插桩（100% 采样）：< 5% 延迟增加
- 启用插桩（1% 采样）：< 1% 延迟增加

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

Apache 2.0 License

## 社区

- 邮件列表：pylinkagent@googlegroups.com
- GitHub Discussions: https://github.com/your-org/PyLinkAgent/discussions
