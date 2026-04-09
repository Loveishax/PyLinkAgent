# PyLinkAgent 验证脚本和 Demo

## 目录结构

```
PyLinkAgent/
├── scripts/                    # 验证脚本目录
│   ├── check_management_service.py   # 检查管理侧服务
│   ├── quick_verify.py               # 快速验证
│   ├── heartbeat_monitor.py          # 心跳监控
│   ├── verify_config_fetch.py        # 配置拉取验证
│   ├── full_verify.py                # 完整验证
│   └── diagnose.py                   # 系统诊断
├── demo/                       # 示例应用目录
│   ├── demo_app.py             # 完整 Demo 应用
│   └── quick_test.py           # 简单测试脚本
└── INTERNAL_NETWORK_VERIFICATION_GUIDE.md  # 详细验证指南
```

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install httpx requests pytest

# 设置环境变量 (可选)
export MANAGEMENT_URL=http://192.168.1.100:9999
export APP_NAME=my-app
export AGENT_ID=agent-001
```

### 2. 快速验证 (30 秒)

```bash
# 方式 1: 使用脚本
python scripts/quick_verify.py http://192.168.1.100:9999

# 方式 2: 使用 demo
python demo/quick_test.py
```

### 3. 完整验证 (60 秒)

```bash
python scripts/full_verify.py http://192.168.1.100:9999
```

### 4. 运行 Demo 应用

```bash
# 运行完整 Demo 应用 (持续运行)
python demo/demo_app.py

# 按 Ctrl+C 退出
```

## 验证脚本说明

### scripts/check_management_service.py
**用途**: 检查管理侧服务是否可访问

**用法**:
```bash
python scripts/check_management_service.py http://192.168.1.100:9999
```

**输出示例**:
```
============================================================
管理侧服务检查
============================================================

管理侧地址：http://192.168.1.100:9999

[OK] 管理侧服务可访问 (HTTP 200)
[OK] /open/agent/heartbeat (POST) - HTTP 200
[OK] /open/service/poll (POST) - HTTP 200

============================================================
```

---

### scripts/quick_verify.py
**用途**: 快速验证与管理侧的基本通信 (推荐首次使用)

**用法**:
```bash
python scripts/quick_verify.py http://192.168.1.100:9999
```

**验证内容**:
1. ExternalAPI 初始化
2. 心跳上报
3. 响应格式验证
4. ACK 端点配置

**预计耗时**: 10 秒

---

### scripts/heartbeat_monitor.py
**用途**: 持续发送心跳并监控响应

**用法**:
```bash
# 默认：发送 6 次心跳，间隔 10 秒
python scripts/heartbeat_monitor.py http://192.168.1.100:9999

# 自定义：间隔 5 秒，发送 10 次
python scripts/heartbeat_monitor.py http://192.168.1.100:9999 my-app agent-001 5 10
```

**环境变量**:
- `HEARTBEAT_INTERVAL`: 心跳间隔 (秒)，默认 10
- `HEARTBEAT_COUNT`: 心跳次数，默认 6

**预计耗时**: 60 秒

---

### scripts/verify_config_fetch.py
**用途**: 验证配置拉取功能

**用法**:
```bash
python scripts/verify_config_fetch.py http://192.168.1.100:9999
```

**验证内容**:
- 影子库配置
- 全局开关
- Redis 影子配置
- ES 影子配置
- 白名单配置

**预计耗时**: 10 秒

---

### scripts/full_verify.py
**用途**: 一键完整验证所有功能

**用法**:
```bash
python scripts/full_verify.py http://192.168.1.100:9999
```

**验证内容**:
1. ExternalAPI 初始化
2. 心跳上报
3. 心跳上报器
4. 配置拉取
5. 配置拉取器

**预计耗时**: 60 秒

---

### scripts/diagnose.py
**用途**: 收集系统诊断信息

**用法**:
```bash
python scripts/diagnose.py
```

**输出内容**:
- 系统信息
- 依赖检查
- PyLinkAgent 模块检查
- 管理侧连通性检查

**预计耗时**: 5 秒

---

## Demo 应用说明

### demo/demo_app.py
**用途**: 完整的示例应用，演示 PyLinkAgent 的所有功能

**功能**:
- 连接管理侧
- 自动心跳上报
- 自动配置拉取
- 配置变更通知
- Pradar 链路追踪演示

**用法**:
```bash
python demo/demo_app.py
```

**运行输出**:
```
============================================================
PyLinkAgent Demo 应用
============================================================

管理侧地址：http://192.168.1.100:9999
应用名称：demo-app
Agent ID: demo-agent-001

[1/5] 初始化 ExternalAPI...
[OK] ExternalAPI 初始化成功

[2/5] 启动心跳上报...
[OK] 心跳上报已启动

[3/5] 启动配置拉取...
[OK] 配置拉取已启动

[4/5] 初次配置拉取...
[OK] 配置拉取成功
     影子库配置：2
     全局开关：5
     URL 白名单：10

[5/5] 模拟业务运行...
[INFO] 按 Ctrl+C 退出

[状态] 运行 10 秒 - 心跳正常 - 配置拉取正常
[状态] 运行 20 秒 - 心跳正常 - 配置拉取正常
  [Pradar] 完成追踪：trace_id=000135671234567...
```

**按 Ctrl+C 退出**

---

### demo/quick_test.py
**用途**: 最简单的测试脚本

**用法**:
```bash
python demo/quick_test.py
```

**输出示例**:
```
管理侧地址：http://192.168.1.100:9999
应用名称：test-app
Agent ID: test-agent-001
----------------------------------------
初始化 ExternalAPI...
[OK] 初始化成功
发送心跳...
[OK] 心跳成功 - 返回 0 个命令
```

---

## 故障排查

### 问题 1: Connection refused
```bash
# 检查服务是否运行
curl -v http://192.168.1.100:9999/open/agent/heartbeat

# 检查防火墙
telnet 192.168.1.100 9999
```

### 问题 2: 404 Not Found
确认使用正确的 API 路径 `/open/agent/heartbeat`

### 问题 3: 500 Internal Server Error
这是正常的，心跳接口仍会返回成功响应。500 可能是因为数据库表结构不完整。

### 问题 4: 配置拉取返回空
管理侧可能没有为该应用配置数据，这是正常的。

---

## 详细文档

详细验证指南请参考：
- [INTERNAL_NETWORK_VERIFICATION_GUIDE.md](INTERNAL_NETWORK_VERIFICATION_GUIDE.md) - 内网验证指南
- [MANAGEMENT_INTEGRATION_VERIFY_REPORT.md](../MANAGEMENT_INTEGRATION_VERIFY_REPORT.md) - 管理侧对接验证报告
- [JAVA_AGENT_ALIGNMENT_REPORT.md](../JAVA_AGENT_ALIGNMENT_REPORT.md) - Java Agent 对齐报告

---

## 支持

如有问题，请收集以下信息：
1. 诊断报告：`python scripts/diagnose.py`
2. 验证日志：`python scripts/full_verify.py 2>&1 | tee verify.log`
