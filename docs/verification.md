# PyLinkAgent 验证方案

本文档只记录已经实际验证过的项目，以及当前建议的验证顺序。

## 1. 已完成的本地验证

### 1.1 编译检查

已对以下文件执行 `py_compile`，结果通过：

- `pylinkagent/__init__.py`
- `pylinkagent/bootstrap.py`
- `pylinkagent/auto_bootstrap.py`
- `pylinkagent/cli.py`
- `pylinkagent/controller/external_api.py`
- `pylinkagent/controller/config_fetcher.py`
- `pylinkagent/controller/heartbeat.py`
- `pylinkagent/controller/command_poller.py`
- `pylinkagent/zookeeper/config.py`
- `sitecustomize.py`

### 1.2 导入检查

以下导入已通过：

- `import pylinkagent`
- `import pylinkagent.auto_bootstrap`
- `import pylinkagent.cli`
- `import sitecustomize`

### 1.3 自动加载烟测

测试环境：

```bash
export PYLINKAGENT_ENABLED=true
export ZK_ENABLED=false
export AUTO_REGISTER_APP=false
export SHADOW_ROUTING=false
```

验证脚本：

```bash
python -c "import pylinkagent; print(pylinkagent.is_running()); pylinkagent.shutdown(); print(pylinkagent.is_running())"
```

已确认：

- `import pylinkagent` 会自动尝试启动探针
- 启动耗时约 `0.66s`
- `shutdown()` 能干净停止后台线程
- 不会被后台线程的初始 `sleep` 长时间卡住

### 1.4 CLI 启动器

已确认：

```bash
pylinkagent-run python -c "import os; print(os.getenv('PYLINKAGENT_ENABLED'))"
```

会输出：

```text
true
```

## 2. 建议的验证顺序

### 2.1 本地静态挂载验证

目标：

- 包已安装
- `sitecustomize` 生效
- 进程能自动加载探针

建议命令：

```bash
python -c "import pylinkagent; print(pylinkagent.is_running())"
```

### 2.2 控制台 HTTP 对接验证

目标：

- `MANAGEMENT_URL` 可达
- 应用注册能成功
- 心跳请求能发出

建议命令：

```bash
python scripts/quick_verify.py
```

说明：

- 这个脚本更适合做“接口可达性检查”
- 它不能证明完整配置消费链路已经闭环

建议同时观察：

- 控制台应用列表
- 控制台探针安装信息
- 控制台最近一次心跳时间
- Python 进程本地日志

### 2.3 ZooKeeper 验证

目标：

- 能连上 ZK
- 在线节点能创建
- 心跳数据能写入

建议先设置：

```bash
export ZK_ENABLED=true
export REGISTER_NAME=zookeeper
export SIMULATOR_ZK_SERVERS=<zk_servers>
export SIMULATOR_APP_NAME=my-python-app
```

当前应优先做真实环境验证，不建议把 `docs/` 中旧的“全部通过”示例当成事实。

建议在 ZK 客户端里重点核对：

- 节点路径是否落在 `/config/log/pradar/client/<app>/<agentId>`
- 节点是否为临时节点
- 节点数据中的 `agentId`、`agentLanguage`、`agentVersion`、`envCode`、`tenantAppKey`
- Python 进程退出后节点是否自动消失

### 2.4 影子路由验证

目标：

- 影子库配置能进入 `ShadowConfigCenter`
- 压测流量命中后发生路由切换

可先运行：

```bash
python scripts/verify_shadow_routing.py
```

说明：

- 该脚本主要验证配置解析和路由逻辑
- 它不等价于真实控制台下发配置并驱动业务连接切换的端到端验证

建议端到端验证 MySQL 时明确分两组流量：

1. 普通流量
   - 预期仍访问业务库
2. 压测标记流量
   - 预期切到影子库

如果暂时没有现成压测标记规范，可以先在入口拦截层约定一个临时 header，例如：

```text
X-PyLinkAgent-Cluster-Test: 1
```

后续再按 Java Agent 和控制台的正式标记规则收敛。

## 3. 当前不应当作通过标准的项目

以下内容在代码里有脚本或骨架，但不能视为“已经完成验证”：

- client path/register/watch 全流程
- 日志服务发现链路
- 命令安装、升级、卸载真实执行
- 全量控制台远程配置消费
- Java Agent 等价的端到端数据隔离

## 4. 推荐的后续验收用例

第一批建议只盯最关键闭环：

1. Python 应用启动后控制台出现应用/探针实例
2. ZK 中出现对应在线临时节点
3. 控制台下发压测开关、白名单开关后，运行时状态能跟着变化
4. 控制台下发影子库配置后，`ConfigFetcher` 能拉到并进入 `ShadowConfigCenter`
5. 带压测标记的 MySQL 流量切到影子库
6. 非压测流量保持业务库不变

## 5. 内网环境建议记录的信息

为了方便远程排查，建议内网验证时把下面信息一并记录下来：

- Python 版本
- 安装方式：`pip install -e .` 还是离线 wheel 安装
- 启动方式：`sitecustomize` / `pylinkagent-run` / 显式导入
- `MANAGEMENT_URL`
- `APP_NAME`
- `AGENT_ID`
- `SIMULATOR_ZK_SERVERS`
- 启动日志完整输出
- 控制台页面截图
- ZK 节点路径和节点数据截图

这些信息足够支撑后续继续做字段对齐和控制台联调。
