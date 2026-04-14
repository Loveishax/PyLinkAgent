# PyLinkAgent 内网验证指南

> **版本**: v2.0.0  
> **更新日期**: 2026-04-14  
> **验证目标**: ZooKeeper 心跳、HTTP 心跳上报、影子数据库配置拉取

---

## 一、验证目标

本指南用于在内网环境中验证 PyLinkAgent 的三个核心功能：

| 功能 | 验证内容 | 依赖 |
|------|----------|------|
| **ZooKeeper 心跳** | ZK 连接、节点创建、心跳刷新 | ZK 集群 (3 节点) |
| **HTTP 心跳上报** | 向 Takin-web 上报心跳 | Takin-web 服务 |
| **影子数据库配置** | 从 Takin-web 拉取影子库配置 | Takin-web + MySQL |

---

## 二、前置条件

### 2.1 环境要求

```bash
# Python 3.8+
python --version

# 安装依赖
pip install -r requirements.txt
```

### 2.2 网络要求

确保内网可以访问以下服务：

| 服务 | 地址 | 用途 |
|------|------|------|
| **ZooKeeper** | `7.198.155.26:2181`<br>`7.198.153.71:2181`<br>`7.198.152.234:2181` | ZK 心跳注册 |
| **Takin-web** | `http://<控制台 IP>:9999` | HTTP 心跳、配置拉取 |
| **MySQL** | `<数据库 IP>:3306` | 影子库路由验证 |

### 2.3 检查网络连通性

```bash
# 检查 ZK 连通性
telnet 7.198.155.26 2181

# 检查 Takin-web 连通性
curl http://<控制台 IP>:9999

# 检查 MySQL 连通性
telnet <数据库 IP> 3306
```

---

## 三、验证步骤

### 步骤 1: 准备配置文件

#### 1.1 创建 ZK 配置文件

创建 `config/zk_config.json`:

```json
{
  "zk_servers": "7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181",
  "app_name": "你的应用名称",
  "agent_id": "your-agent-id",
  "env_code": "test",
  "tenant_id": "1",
  "user_id": "",
  "tenant_app_key": "",
  "tro_web_url": "http://<控制台 IP>:9999"
}
```

#### 1.2 设置环境变量

```bash
# Windows PowerShell
$env:MANAGEMENT_URL="http://<控制台 IP>:9999"
$env:APP_NAME="your-app-name"
$env:AGENT_ID="your-agent-id"
$env:SIMULATOR_ENV_CODE="test"
$env:SIMULATOR_TENANT_ID="1"
$env:ZK_ENABLED="true"
$env:REGISTER_NAME="zookeeper"
$env:AUTO_REGISTER_APP="true"
```

```bash
# Linux/Mac
export MANAGEMENT_URL="http://<控制台 IP>:9999"
export APP_NAME="your-app-name"
export AGENT_ID="your-agent-id"
export SIMULATOR_ENV_CODE="test"
export SIMULATOR_TENANT_ID="1"
export ZK_ENABLED="true"
export REGISTER_NAME="zookeeper"
export AUTO_REGISTER_APP="true"
```

---

### 步骤 2: 验证 ZooKeeper 心跳

#### 2.1 运行 ZK 测试脚本

```bash
cd PyLinkAgent
python scripts/test_zk_integration.py
```

**预期输出**:
```
=== 测试 ZK 配置加载 ===
ZK 服务器：7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181
[OK] ZK 配置加载成功

=== 测试 ZK 客户端连接 ===
[OK] ZK 连接成功
[OK] 临时节点创建成功

=== 测试心跳管理器 ===
[OK] 心跳管理器初始化成功
[OK] 心跳管理器启动成功
等待 35 秒观察心跳刷新...
[OK] 心跳节点存活
```

#### 2.2 验证 ZK 节点

使用 ZK 命令行工具检查节点：

```bash
# 连接到 ZK
zkCli.sh -server 7.198.155.26:2181

# 查看状态路径
ls /config/log/pradar/status/你的应用名称

# 查看心跳节点数据
get /config/log/pradar/status/你的应用名称/你的 AgentID

# 观察节点是否为临时节点
stat /config/log/pradar/status/你的应用名称/你的 AgentID
# ephemeralOwner 应该不为 0
```

---

### 步骤 3: 验证 HTTP 心跳上报

#### 3.1 运行心跳验证脚本

```bash
python scripts/verify_heartbeat_full.py
```

**预期输出**:
```
============================================================
PyLinkAgent 心跳上报验证
============================================================
管理侧地址：http://<控制台 IP>:9999
应用名称：your-app-name
Agent ID: your-agent-id

[步骤 1/4] 检查管理侧连通性...
      [OK] 管理侧服务可访问
[步骤 2/4] 初始化 ExternalAPI...
      [OK] ExternalAPI 初始化成功
[步骤 3/4] 发送心跳请求...
      [OK] 心跳上报成功
[步骤 4/4] 等待并再次上报...
      [OK] 心跳上报成功

验证完成!
```

#### 3.2 在 Takin-web 控制台验证

1. 登录 Takin-web 控制台
2. 进入「应用管理」页面
3. 找到你的应用
4. 查看「探针实例」或「节点列表」
5. 应该能看到新注册的 Agent 节点
6. 心跳状态应该显示为「正常」或「运行中」

---

### 步骤 4: 验证影子数据库配置拉取

#### 4.1 在 Takin-web 中配置影子库

1. 登录 Takin-web 控制台
2. 进入「应用管理」→ 选择你的应用
3. 进入「数据源配置」或「影子库配置」
4. 添加影子库映射:
   - 主库 JDBC URL: `jdbc:mysql://<主库 IP>:3306/your_db`
   - 影子库 JDBC URL: `jdbc:mysql://<影子库 IP>:3306/your_db_shadow`
   - 用户名/密码

#### 4.2 运行配置拉取验证脚本

```bash
python scripts/verify_config_fetch.py
```

**预期输出**:
```
============================================================
配置拉取验证
============================================================
管理侧地址：http://<控制台 IP>:9999
应用名称：your-app-name

[INFO] 开始拉取配置...
[OK] 影子库配置拉取成功
  数据源：master
  主库：jdbc:mysql://master:3306/your_db
  影子库：jdbc:mysql://shadow:3306/your_db_shadow
```

#### 4.3 验证配置内容

```bash
python scripts/verify_config_full.py
```

---

### 步骤 5: 完整功能验证（一键验证）

运行快速启动脚本，同时验证所有功能：

```bash
python scripts/quickstart_agent.py
```

**预期输出**:
```
============================================================
PyLinkAgent 快速启动
============================================================
控制台地址：http://<控制台 IP>:9999
应用名称：your-app-name
注册中心：zookeeper
ZK 启用：true
============================================================
PyLinkAgent 启动中...
初始化 ExternalAPI:
  控制台地址：http://<控制台 IP>:9999
  应用名称：your-app-name
注册应用...
  应用注册成功
初始化 ZooKeeper 集成...
  ZooKeeper 集成已启用
启动配置拉取器 (间隔：60 秒)
启动 HTTP 心跳上报 (间隔：60 秒)
启动命令轮询 (间隔：30 秒)
============================================================
PyLinkAgent 启动完成
  HTTP 心跳：启用
  ZK 心跳：启用
  应用注册：已注册
============================================================
```

---

## 四、验证清单

### 4.1 ZooKeeper 心跳验证

- [ ] ZK 客户端连接成功
- [ ] 在 ZK 中创建临时节点 `/config/log/pradar/status/{app}/{agentId}`
- [ ] 节点数据包含完整的心跳信息（JSON 格式）
- [ ] 节点为临时节点（ephemeral）
- [ ] 心跳数据每 30 秒刷新一次
- [ ] 断开连接后节点自动删除
- [ ] 重连后节点自动重建

### 4.2 HTTP 心跳上报验证

- [ ] ExternalAPI 初始化成功
- [ ] 心跳接口返回成功
- [ ] Takin-web 控制台显示 Agent 在线
- [ ] 心跳时间戳持续更新
- [ ] 控制台能接收命令并返回

### 4.3 影子库配置拉取验证

- [ ] 配置拉取接口返回成功
- [ ] 影子库配置包含主库和影子库 URL
- [ ] 配置数据格式正确
- [ ] 定时同步配置（60 秒间隔）

---

## 五、故障排查

### 5.1 ZK 连接失败

**问题**: 无法连接到 ZooKeeper

```bash
# 检查 ZK 服务
echo ruok | nc 7.198.155.26 2181
# 应返回：imok

# 检查防火墙
netsh advfirewall show allprofiles  # Windows
sudo ufw status  # Linux

# 测试 kazoo 连接
python -c "from kazoo.client import KazooClient; c=KazooClient('7.198.155.26:2181'); c.start(); print(c.connected)"
```

### 5.2 HTTP 心跳失败

**问题**: 心跳上报返回错误

```bash
# 检查 Takin-web 是否运行
curl http://<控制台 IP>:9999

# 检查应用是否已注册
# 在数据库中查询
SELECT * FROM t_application_mnt WHERE APPLICATION_NAME = 'your-app';

# 查看日志
tail -f logs/pylinkagent.log
```

### 5.3 配置拉取返回空

**问题**: 影子库配置拉取返回空

**解决方案**:
1. 在 Takin-web 中确认应用已创建
2. 确认影子库配置已添加
3. 检查数据库表 `t_shadow_table_datasource` 是否有配置

```sql
-- 查询影子库配置
SELECT * FROM t_shadow_table_datasource WHERE APPLICATION_NAME = 'your-app';
```

---

## 六、日志查看

### 6.1 日志文件位置

```
PyLinkAgent/logs/
├── pylinkagent.log      # 主日志
├── zk_client.log        # ZK 客户端日志
└── external_api.log     # HTTP API 日志
```

### 6.2 关键日志关键字

```bash
# ZK 连接
grep "ZK 连接成功" logs/*.log

# 心跳上报
grep "心跳上报成功" logs/*.log

# 配置拉取
grep "配置拉取成功" logs/*.log

# 错误信息
grep -i "error\|fail" logs/*.log
```

---

## 七、验证报告模板

验证完成后，填写以下报告：

```markdown
## PyLinkAgent 内网验证报告

**验证日期**: 2026-XX-XX
**验证环境**: 内网
**验证人**: XXX

### 验证结果

| 功能 | 状态 | 备注 |
|------|------|------|
| ZooKeeper 心跳 | ✅/❌ | |
| HTTP 心跳上报 | ✅/❌ | |
| 影子库配置拉取 | ✅/❌ | |

### 问题记录

1. [问题描述]
   - 原因：
   - 解决方案：

### 结论

[验证通过/需要改进]
```

---

## 八、相关文档

- [ZooKeeper 集成文档](docs/ZOOKEEPER_INTEGRATION.md)
- [应用自动注册文档](docs/APPLICATION_REGISTRY.md)
- [部署指南](DEPLOYMENT_GUIDE.md)
- [架构设计](docs/architecture.md)

---

**文档完成日期**: 2026-04-14  
**版本**: v1.0
