# PyLinkAgent

PyLinkAgent 当前的目标不是一次性补齐 Java LinkAgent 的全部插件生态，而是优先打通这条可验证主链路：

1. Python 进程静态挂载探针
2. 探针向控制台上报应用和心跳
3. 探针从控制台拉取影子配置
4. 识别压测流量
5. 将 MySQL 写流量切到影子库

这条链路现在已经具备本地闭环验证能力，并且已经用真实本地 MySQL 跑通了 FastAPI demo。

## 当前状态

已经落地：

- `sitecustomize` 自动挂载
- `pylinkagent-run` 启动包装
- `bootstrap` 主链路收敛
- 控制台 HTTP 注册 / 心跳 / 配置拉取骨架接通
- ZooKeeper 在线节点基础接通
- Flask / FastAPI HTTP 入口染色
- MySQL / SQLAlchemy / Redis / ES / Kafka / HTTP 影子路由拦截骨架
- 远程压测开关、白名单开关、远程调用白名单、DB/Redis/ES/Kafka 配置进入运行时
- FastAPI + MySQL 真实数据库 demo

仍未闭环：

- 控制台命令安装 / 升级 / 卸载的真实执行
- ZK watch / 日志服务发现 / 完整日志上报链路
- 更大范围的中间件插件生态

## 现在是否可以去内网做全链路验证

可以，前提是你按 demo 和文档准备以下条件：

- Python 项目能通过 `sitecustomize` 或 `pylinkagent-run` 挂载探针
- 控制台可以访问
- ZooKeeper 可以访问
- 控制台上为目标应用配置压测总开关和影子库配置
- 目标业务使用 `pymysql` 或 SQLAlchemy MySQL

只要这些条件具备，你现在就可以在内网验证这条链路：

`挂载探针 -> 控制台看到应用/探针 -> 探针拉到影子库配置 -> 带压测 header 的请求进入 -> 写入影子库`

## 安装

```bash
cd PyLinkAgent
pip install -r requirements.txt
pip install -e .
```

内网离线安装说明见 [docs/quickstart.md](docs/quickstart.md)。

## 启动方式

### 1. `sitecustomize` 自动加载

最接近 Java `-javaagent` 的使用方式。

```bash
export PYLINKAGENT_ENABLED=true
export MANAGEMENT_URL=http://localhost:9999
export APP_NAME=my-python-app
export AGENT_ID=my-python-agent
python app.py
```

### 2. `pylinkagent-run`

```bash
pylinkagent-run python app.py
```

### 3. 显式导入

```python
import os

os.environ["PYLINKAGENT_ENABLED"] = "true"
os.environ["MANAGEMENT_URL"] = "http://localhost:9999"
os.environ["APP_NAME"] = "my-python-app"

import pylinkagent
```

## FastAPI + MySQL Demo

用于验证最关键的数据隔离链路。

- 目录：`examples/fastapi_mysql_shadow_demo/`
- 文档：[examples/fastapi_mysql_shadow_demo/README.md](examples/fastapi_mysql_shadow_demo/README.md)
- 初始化数据库：

```bash
python examples/fastapi_mysql_shadow_demo/init_demo_db.py
```

本地已实际验证通过：

- 普通请求写入 `pylinkagent_demo_biz`
- 带 `X-Pradar-Cluster-Test: 1` 的请求写入 `pylinkagent_demo_shadow`
- `GET /debug/runtime` 可返回当前探针运行快照
- 压测流量下游 HTTP 调用会自动透传 `X-Pradar-Cluster-Test: 1`

## 已完成验证

本地已通过：

- `python -m py_compile`
- 自动加载烟测
- 运行时配置同步测试
- 控制台字段对齐测试
- HTTP 入口染色测试
- MySQL 影子路由测试
- FastAPI + MySQL 真实数据库端到端测试

核心命令：

```bash
python -m pytest tests/test_runtime_config_sync.py -q
python -m pytest tests/test_control_plane_alignment.py -q
python -m pytest tests/test_http_ingress_tracing.py -q
python -m pytest tests/test_shadow_mysql_routing.py -q
python -m pytest tests/test_fastapi_demo_e2e.py -q
python -m pytest tests/test_http_shadow_propagation.py -q
```

联调诊断：

```bash
python scripts/diagnose.py
python scripts/diagnose.py http://127.0.0.1:8000
```

## 文档索引

- [快速开始](docs/quickstart.md)
- [验证方案](docs/verification.md)
- [当前架构](docs/architecture.md)
- [ZooKeeper 集成现状](docs/ZOOKEEPER_INTEGRATION.md)
- [影子路由现状](docs/SHADOW_ROUTING_GUIDE.md)
- [FastAPI MySQL Demo](examples/fastapi_mysql_shadow_demo/README.md)
