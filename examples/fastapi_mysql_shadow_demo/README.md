# FastAPI MySQL Shadow Demo

这个 demo 的目标很单纯：验证下面这条链路已经打通。

`FastAPI 请求进入 -> 探针识别压测 header -> 业务代码仍然只连业务库 -> 探针把 pymysql.connect() 改写到影子库`

## 1. 数据库准备

默认使用本机 MySQL：

- host: `localhost`
- port: `3306`
- user: `root`
- password: `123456`

初始化命令：

```bash
cd PyLinkAgent
python examples/fastapi_mysql_shadow_demo/init_demo_db.py
```

会创建两个库：

- `pylinkagent_demo_biz`
- `pylinkagent_demo_shadow`

两个库都会创建表：

- `demo_users`

## 2. 离线 demo 模式

这个模式不依赖控制台，适合先验证探针挂载和 MySQL 影子路由。

### 2.1 启动

Linux/macOS：

```bash
cd PyLinkAgent
export PYLINKAGENT_ENABLED=true
export AUTO_REGISTER_APP=false
export ZK_ENABLED=false
export SHADOW_ROUTING=true
export HTTP_SERVER_TRACING=true
export APP_NAME=fastapi-shadow-demo
export DEMO_LOCAL_SHADOW_CONFIG=true
export DEMO_LOCAL_CLUSTER_TEST_SWITCH=true
uvicorn examples.fastapi_mysql_shadow_demo.app:app --host 0.0.0.0 --port 8000
```

Windows PowerShell：

```powershell
cd PyLinkAgent
$env:PYLINKAGENT_ENABLED="true"
$env:AUTO_REGISTER_APP="false"
$env:ZK_ENABLED="false"
$env:SHADOW_ROUTING="true"
$env:HTTP_SERVER_TRACING="true"
$env:APP_NAME="fastapi-shadow-demo"
$env:DEMO_LOCAL_SHADOW_CONFIG="true"
$env:DEMO_LOCAL_CLUSTER_TEST_SWITCH="true"
uvicorn examples.fastapi_mysql_shadow_demo.app:app --host 0.0.0.0 --port 8000
```

### 2.2 验证请求

普通请求：

```bash
curl -X POST http://127.0.0.1:8000/users -H "Content-Type: application/json" -d "{\"name\":\"normal-user\"}"
```

压测请求：

```bash
curl -X POST http://127.0.0.1:8000/users -H "X-Pradar-Cluster-Test: 1" -H "Content-Type: application/json" -d "{\"name\":\"pressure-user\"}"
```

预期：

- 普通请求返回 `database=pylinkagent_demo_biz`
- 压测请求返回 `database=pylinkagent_demo_shadow`

运行时快照：

```bash
curl http://127.0.0.1:8000/debug/runtime
```

重点关注：

- `running`
- `cluster_test_switch_enabled`
- `shadow_db_config_count`
- `db_mappings`

如果 demo 里还会再调下游 HTTP 服务，当前探针也会自动透传：

- `X-Pradar-Cluster-Test: 1`

## 3. 控制台联调模式

如果要验证真实全链路，把下面两个本地开关关掉：

```text
DEMO_LOCAL_SHADOW_CONFIG=false
DEMO_LOCAL_CLUSTER_TEST_SWITCH=false
```

然后改为使用控制台和 ZK：

```bash
export MANAGEMENT_URL=http://<takin-web-host>:<port>
export AGENT_ID=<plain-agent-id>
export AUTO_REGISTER_APP=true
export ZK_ENABLED=true
export REGISTER_NAME=zookeeper
export SIMULATOR_ZK_SERVERS=<zk1:2181,zk2:2181,zk3:2181>
export SIMULATOR_APP_NAME=fastapi-shadow-demo
export SIMULATOR_AGENT_ID=<plain-agent-id>
export SIMULATOR_ENV_CODE=<env-code>
export SIMULATOR_USER_ID=<user-id>
export SIMULATOR_TENANT_APP_KEY=<tenant-app-key>
```

控制台上至少要配置：

- 应用名：`fastapi-shadow-demo`
- 压测总开关：打开
- 业务 JDBC URL：`jdbc:mysql://<mysql-host>:3306/pylinkagent_demo_biz`
- 影子 JDBC URL：`jdbc:mysql://<mysql-host>:3306/pylinkagent_demo_shadow`
- `dsType=0`

## 4. 本地已验证结果

当前仓库已经有真实端到端测试：

```bash
python -m pytest tests/test_fastapi_demo_e2e.py -q
```

该测试会：

1. 初始化真实本地 MySQL
2. 启动 PyLinkAgent
3. 挂载 FastAPI demo
4. 发送普通请求和压测请求
5. 校验业务库和影子库的数据分别增长
