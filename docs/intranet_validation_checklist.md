# PyLinkAgent 内网验证清单

这份清单只关注当前最关键的主链路：

`挂载 agent -> 控制台看到应用/探针 -> ZK 在线节点 -> 拉到影子配置 -> 识别压测流量 -> 写入 MySQL 影子库`

建议按顺序执行，不要一上来同时排查控制台、ZK、影子库和业务代码。

## 0. 准备信息

- 应用名：`________________`
- Agent ID：`________________`
- 控制台地址：`________________`
- ZooKeeper 地址：`________________`
- 业务库 JDBC URL：`________________`
- 影子库 JDBC URL：`________________`

## 1. 挂载验证

- [ ] 业务应用已挂载探针
- [ ] 启动日志出现 `PyLinkAgent 启动中`
- [ ] `/debug/runtime` 返回 `200`
- [ ] `/debug/runtime` 中 `running=true`

## 2. 控制台在线验证

- [ ] 控制台页面出现目标应用
- [ ] 控制台页面出现 Python 探针安装信息
- [ ] 心跳时间持续刷新
- [ ] 页面展示的应用名正确
- [ ] 页面展示的 `agentId` 正确

## 3. ZooKeeper 节点验证

- [ ] 路径 `/config/log/pradar/client/<appName>/<fullAgentId>` 存在
- [ ] 节点为临时节点
- [ ] 节点内容包含 `agentLanguage=PYTHON`
- [ ] 节点内容包含 `agentId`
- [ ] 节点内容包含 `agentVersion`
- [ ] 节点内容包含 `simulatorVersion`
- [ ] 节点内容包含 `pid`
- [ ] 节点内容包含 `envCode`
- [ ] 节点内容包含 `tenantAppKey`

## 4. 控制台配置下发验证

- [ ] 控制台已打开压测总开关
- [ ] 控制台已配置影子库
- [ ] 业务 JDBC URL 填写正确
- [ ] 影子 JDBC URL 填写正确
- [ ] `dsType=0`
- [ ] 日志中出现 `Pradar 运行时配置已应用`
- [ ] 日志中出现 `影子配置已更新`
- [ ] `/debug/runtime` 中 `cluster_test_switch_enabled=true`
- [ ] `/debug/runtime` 中 `shadow_db_config_count > 0`
- [ ] `/debug/runtime` 中 `db_mappings` 包含业务库和影子库映射

## 5. MySQL 隔离验证

普通请求：

- [ ] 不带 `X-Pradar-Cluster-Test: 1`
- [ ] 返回结果显示业务库
- [ ] 数据只写入业务库

压测请求：

- [ ] 带 `X-Pradar-Cluster-Test: 1`
- [ ] 返回结果显示影子库
- [ ] 日志出现 `MySQL rerouted to shadow DB`
- [ ] 数据只写入影子库

最终结论：

- [ ] 普通流量只写业务库
- [ ] 压测流量只写影子库

## 6. 下游 HTTP 透传验证

如果当前服务还会调用下游 HTTP 服务：

- [ ] 下游服务收到 `X-Pradar-Cluster-Test: 1`

## 7. 诊断命令

```bash
python scripts/diagnose.py
python scripts/diagnose.py http://127.0.0.1:8000
```

重点字段：

- `running`
- `management_url`
- `app_name`
- `agent_id`
- `zk_running`
- `config_fetcher_running`
- `cluster_test_switch_enabled`
- `shadow_db_config_count`
- `db_mappings`

## 8. 验证完成后回传的信息

- 启动命令
- 关键环境变量
- 完整启动日志
- 控制台截图
- ZK 节点路径和内容截图
- `/debug/runtime` 返回 JSON
- 普通请求和压测请求的返回结果
- 业务库和影子库的查询结果
