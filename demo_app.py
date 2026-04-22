"""
PyLinkAgent Demo Application — 真实 MySQL 影子路由演示

使用本地 MySQL 验证完整影子路由:
  业务库: wefire_db_sit (root@localhost:3306)
  影子库: pt_wefire_db_sit (root@localhost:3306)

两门影子路由决策:
  Gate 1: PradarSwitcher.is_cluster_test_enabled() — 全局压测开关
  Gate 2: Pradar.is_cluster_test()               — 当前请求流量染色

  ShadowRouter.should_route() = Gate1 && Gate2

数据流:
  HTTP Request → Middleware 检测 Header → Pradar 压测标记
    → ShadowRouter.route_mysql() 生成影子连接参数
    → pymysql.connect(shadow_params) → 真实影子库查询
    → Pradar.end_trace() 清理
"""

import os
import pymysql
from pymysql.cursors import DictCursor
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

# ==================== PyLinkAgent 影子路由模块 ====================

from pylinkagent.pradar import Pradar, PradarSwitcher
from pylinkagent.shadow import (
    get_router, get_config_center,
    ShadowDatabaseConfig, ShadowSQLRewriter,
)

logger = logging.getLogger(__name__)

# ==================== 数据库配置 ====================

BUSINESS_DB = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "wefire_db_sit",
    "charset": "utf8mb4",
}

SHADOW_DB = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "pt_wefire_db_sit",
    "charset": "utf8mb4",
}

# JDBC URL (用于 ShadowRouter 配置注册)
BUSINESS_JDBC_URL = "jdbc:mysql://localhost:3306/wefire_db_sit"

app = FastAPI(
    title="PyLinkAgent Demo — 真实 MySQL 影子路由",
    description="使用本地 MySQL 验证完整影子路由流程",
    version="3.0",
)


# ==================== 影子路由中间件 ====================

@app.middleware("http")
async def shadow_routing_middleware(request: Request, call_next):
    """
    影子路由中间件 — 核心两门决策

    每个请求经过此中间件:
    1. 检测 x-pressure-test Header
    2. PradarSwitcher 打开全局开关 (Gate 1)
    3. Pradar 创建 Trace 并标记压测 (Gate 2)
    4. ShadowRouter.should_route() = Gate1 && Gate2
    5. ShadowRouter.route_mysql() 生成影子连接参数
    6. 存入 request.state 供业务端点使用
    7. 请求结束后清理 Pradar 上下文
    """
    is_pressure = (
        request.headers.get("x-pressure-test", "").lower() == "true"
        or request.headers.get("x-shadow-flag") is not None
    )

    routing = {
        "is_pressure_header": is_pressure,
        "gate1_global_switch": False,
        "gate2_traffic_dye": False,
        "should_route": False,
        "target": "business",
        "trace_id": "",
    }

    try:
        if is_pressure:
            PradarSwitcher.turn_cluster_test_switch_on()
            routing["gate1_global_switch"] = True

            ctx = Pradar.start_trace("demo-app", "web", request.url.path)
            Pradar.set_cluster_test(True)
            routing["gate2_traffic_dye"] = True
            routing["trace_id"] = ctx.trace_id
            Pradar.set_user_data("source", "demo_middleware")

        router = get_router()
        should_route = router.should_route()
        routing["should_route"] = should_route
        routing["target"] = "shadow" if should_route else "business"

        # ShadowRouter.route_mysql() 在 Pradar 上下文中生成影子连接参数
        if should_route:
            shadow_conn = router.route_mysql(
                original_url=BUSINESS_JDBC_URL,
                original_username=BUSINESS_DB["user"],
            )
            if shadow_conn and "host" in shadow_conn:
                routing["shadow_mysql"] = {
                    "host": shadow_conn.get("host"),
                    "port": shadow_conn.get("port"),
                    "database": shadow_conn.get("database"),
                    "user": shadow_conn.get("user"),
                }

        request.state.routing = routing
        response = await call_next(request)
        return response

    finally:
        if Pradar.has_context():
            Pradar.end_trace()


# ==================== 数据库查询函数 ====================

def query_business(sql: str, params=None) -> List[Dict]:
    """查询业务库"""
    conn = pymysql.connect(**BUSINESS_DB)
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()


def query_shadow(sql: str, params=None) -> List[Dict]:
    """查询影子库"""
    conn = pymysql.connect(**SHADOW_DB)
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()


def query_routed(sql: str, params=None, request: Request = None):
    """
    路由查询 — 根据中间件决策选择业务库或影子库

    在真实环境中，这会被 wrapt 拦截器自动完成:
    pymysql.connect(host='localhost') → 拦截 → connect(host=shadow_host, db=shadow_db)
    """
    routing = getattr(getattr(request, "state", None), "routing", {})
    is_shadow = routing.get("should_route", False)

    if is_shadow:
        data = query_shadow(sql, params)
    else:
        data = query_business(sql, params)

    return {
        "data": data,
        "routing": {
            "target": "shadow" if is_shadow else "business",
            "database": SHADOW_DB["database"] if is_shadow else BUSINESS_DB["database"],
            "gate1_global_switch": routing.get("gate1_global_switch", False),
            "gate2_traffic_dye": routing.get("gate2_traffic_dye", False),
            "trace_id": routing.get("trace_id", ""),
        },
    }


# ==================== 业务端点 ====================

@app.get("/", response_class=HTMLResponse)
def index():
    """首页"""
    return """
<!DOCTYPE html><html><head><title>PyLinkAgent — 真实 MySQL 影子路由</title>
<style>body{font-family:monospace;margin:40px;background:#1a1a2e;color:#e0e0e0}
.container{max-width:900px;margin:0 auto}
h1{color:#00d4ff}h2{color:#7b68ee;margin-top:30px}
.endpoint{background:#16213e;padding:12px;margin:8px 0;border-radius:4px;border-left:3px solid #00d4ff}
.method{color:#00d4ff;font-weight:bold}
code{background:#0f3460;padding:2px 8px;border-radius:3px}
.pressure{background:#1a1a3e;border-left-color:#ff6b6b}
.info{background:#0f3460;padding:15px;margin-top:15px;border-radius:4px}
.db-info{display:flex;gap:20px;margin:10px 0}
.db-card{flex:1;background:#16213e;padding:15px;border-radius:4px}
.db-card h3{margin:0 0 8px 0;color:#00d4ff}
.arrow{text-align:center;font-size:24px;color:#ff6b6b}
</style></head><body><div class="container">
<h1>PyLinkAgent — 真实 MySQL 影子路由</h1>
<p>使用本地 MySQL 验证完整影子路由流程</p>

<h2>数据库配置</h2>
<div class="db-info">
<div class="db-card"><h3>业务库</h3><code>wefire_db_sit</code><br>root@localhost:3306<br>3 users, 3 orders, 2 products</div>
<div class="db-card"><h3>影子库</h3><code>pt_wefire_db_sit</code><br>root@localhost:3306<br>3 shadow users, 3 shadow orders, 2 shadow products</div>
</div>

<h2>API 端点</h2>
<div class="endpoint"><span class="method">GET</span> <code>/health</code> 健康检查</div>
<div class="endpoint"><span class="method">GET</span> <code>/api/users</code> 用户列表 (真实 MySQL)</div>
<div class="endpoint"><span class="method">GET</span> <code>/api/users/{id}</code> 用户详情</div>
<div class="endpoint"><span class="method">GET</span> <code>/api/orders</code> 订单列表</div>
<div class="endpoint"><span class="method">GET</span> <code>/api/products</code> 商品列表</div>
<div class="endpoint"><span class="method">GET</span> <code>/api/chain/{user_id}</code> 链路调用 (跨表)</div>
<div class="endpoint pressure"><span class="method">GET</span> <code>/api/sql/rewrite?sql=...</code> SQL 重写</div>
<div class="endpoint"><span class="method">GET</span> <code>/db/query?sql=...</code> 执行任意 SQL</div>
<div class="endpoint"><span class="method">GET</span> <code>/routing/decision</code> 两门决策详情</div>
<div class="endpoint"><span class="method">GET</span> <code>/routing/mysql</code> ShadowRouter 连接参数</div>
<div class="endpoint pressure"><span class="method">POST</span> <code>/switch/cluster_test</code> 压测开关控制</div>

<h2>测试命令</h2>
<div class="info">
<p><code>curl http://localhost:8000/api/users</code> — 业务库</p>
<p><code>curl -H "x-pressure-test: true" http://localhost:8000/api/users</code> — 影子库</p>
<p><code>curl -H "x-pressure-test: true" http://localhost:8000/db/query?sql=SELECT%20*%20FROM%20users</code> — 任意 SQL</p>
</div></div></body></html>
"""


@app.get("/health")
def health():
    """健康检查 + 数据库连通性"""
    try:
        conn = pymysql.connect(**BUSINESS_DB)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            user_count = cur.fetchone()[0]
        conn.close()
        db_status = "ok"
    except Exception as e:
        user_count = None
        db_status = f"error: {e}"

    return {
        "status": "healthy",
        "service": "pylinkagent-demo-v3",
        "business_db": db_status,
        "business_db_users": user_count,
        "cluster_test_switch": PradarSwitcher.is_cluster_test_enabled(),
    }


@app.get("/api/users")
def list_users(request: Request):
    """用户列表 — 真实 MySQL 查询"""
    return query_routed("SELECT * FROM users ORDER BY id", request=request)


@app.get("/api/users/{user_id}")
def get_user(user_id: int, request: Request):
    """用户详情"""
    result = query_routed("SELECT * FROM users WHERE id = %s", (user_id,), request=request)
    return result


@app.get("/api/orders")
def list_orders(request: Request):
    """订单列表"""
    return query_routed("SELECT * FROM orders ORDER BY id", request=request)


@app.get("/api/products")
def list_products(request: Request):
    """商品列表"""
    return query_routed("SELECT * FROM products ORDER BY id", request=request)


# ==================== 链路调用演示 ====================

@app.get("/api/chain/{user_id}")
def chain_call(user_id: int, request: Request):
    """
    链路调用演示

    在同一个请求中查询用户 + 订单，展示影子路由的一致性
    """
    routing = getattr(request.state, "routing", {})
    is_shadow = routing.get("should_route", False)

    if is_shadow:
        users = query_shadow("SELECT * FROM users WHERE id = %s", (user_id,))
        orders = query_shadow("SELECT * FROM orders WHERE user_id = %s", (user_id,))
    else:
        users = query_business("SELECT * FROM users WHERE id = %s", (user_id,))
        orders = query_business("SELECT * FROM orders WHERE user_id = %s", (user_id,))

    return {
        "user": users[0] if users else None,
        "orders": orders,
        "routing": {
            "target": "shadow" if is_shadow else "business",
            "database": SHADOW_DB["database"] if is_shadow else BUSINESS_DB["database"],
            "trace_id": routing.get("trace_id", ""),
            "gate1_switch": routing.get("gate1_global_switch", False),
            "gate2_dye": routing.get("gate2_traffic_dye", False),
        },
    }


# ==================== SQL 重写 ====================

@app.get("/api/sql/rewrite")
def sql_rewrite(
    sql: str = "SELECT * FROM users WHERE id = 1",
    request: Request = None,
):
    """
    SQL 重写演示

    ShadowSQLRewriter 将业务表名替换为影子表名
    """
    routing = getattr(getattr(request, "state", None), "routing", {})
    is_shadow = routing.get("should_route", False)

    table_mapping = {
        "users": "shadow_users",
        "orders": "shadow_orders",
        "products": "shadow_products",
    }

    rewriter = ShadowSQLRewriter(table_mapping)
    rewritten = rewriter.rewrite(sql) if is_shadow else sql

    return {
        "original_sql": sql,
        "rewritten_sql": rewritten,
        "target": "shadow" if is_shadow else "business",
        "table_mapping": table_mapping,
        "needs_rewrite": rewriter.needs_rewrite(sql),
    }


# ==================== 任意 SQL 查询 ====================

@app.get("/db/query")
def execute_query(
    sql: str = "SELECT * FROM users",
    request: Request = None,
):
    """
    执行任意 SQL 查询

    根据中间件路由决策选择业务库或影子库
    """
    return query_routed(sql, request=request)


# ==================== 影子配置管理 ====================

class ShadowConfigInput(BaseModel):
    ds_type: int = 0
    url: str
    username: str = ""
    password: Optional[str] = None
    shadow_url: str = ""
    shadow_username: str = ""
    shadow_password: Optional[str] = None
    business_shadow_tables: Dict[str, str] = {}


@app.post("/shadow/config")
def register_shadow_config(config: ShadowConfigInput):
    """注册影子库配置到 ShadowConfigCenter"""
    shadow_config = ShadowDatabaseConfig(
        ds_type=config.ds_type,
        url=config.url,
        username=config.username,
        password=config.password,
        shadow_url=config.shadow_url,
        shadow_username=config.shadow_username,
        shadow_password=config.shadow_password,
        business_shadow_tables=config.business_shadow_tables,
    )
    get_config_center().register_db_config(shadow_config)
    return {"status": "ok", "config_url": config.url, "shadow_url": config.shadow_url}


@app.get("/shadow/status")
def shadow_status():
    """影子配置状态"""
    cc = get_config_center()
    router = get_router()
    all_configs = cc.get_all_db_configs()

    return {
        "config_count": len(all_configs),
        "router_shadow_enabled": router.is_shadow_enabled(),
        "configs": [
            {
                "url": c.url,
                "shadow_url": c.shadow_url,
                "ds_type": c.ds_type,
                "tables": list(c.business_shadow_tables.keys()),
            }
            for c in all_configs.values()
        ],
    }


# ==================== 两门决策详情 ====================

@app.get("/routing/decision")
def routing_decision(
    request: Request = None,
    x_pressure_test: Optional[str] = Header(None),
):
    """展示当前请求经过两门决策的完整信息"""
    routing = getattr(getattr(request, "state", None), "routing", {})

    ctx_info = {}
    if Pradar.has_context():
        ctx = Pradar.get_context()
        ctx_info = {
            "trace_id": ctx.trace_id,
            "invoke_id": ctx.invoke_id,
            "service": ctx.service_name,
            "method": ctx.method_name,
            "cluster_test": ctx.is_cluster_test(),
            "user_data": ctx.user_data,
        }

    return {
        "routing": routing,
        "pradar": {
            "has_context": Pradar.has_context(),
            "context": ctx_info,
            "trace_id": Pradar.get_trace_id(),
            "is_cluster_test": Pradar.is_cluster_test(),
        },
        "pradar_switcher": {
            "cluster_test_enabled": PradarSwitcher.is_cluster_test_enabled(),
            "cluster_test_switch": PradarSwitcher._cluster_test_switch,
        },
    }


# ==================== ShadowRouter 连接参数 ====================

@app.get("/routing/mysql")
def route_mysql_demo(
    request: Request = None,
    x_pressure_test: Optional[str] = Header(None),
):
    """
    演示 ShadowRouter.route_mysql() 真实生成影子连接参数

    生产环境中，wrapt 拦截器会:
    1. 拦截 pymysql.connect(host='localhost', db='wefire_db_sit')
    2. 调用 ShadowRouter.route_mysql() 获取影子连接参数
    3. 替换为 ShadowRouter 返回的影子库参数
    """
    routing = getattr(getattr(request, "state", None), "routing", {})
    shadow_mysql = routing.get("shadow_mysql")

    return {
        "routing_decision": routing,
        "business_connection": BUSINESS_DB,
        "shadow_connection": shadow_mysql,
        "interceptor_behavior": (
            f"pymysql.connect(host='{BUSINESS_DB['host']}', db='{BUSINESS_DB['database']}') "
            f"→ 压测流量，拦截替换 → "
            f"connect(host='{shadow_mysql['host']}', db='{shadow_mysql['database']}')"
            if shadow_mysql else
            "无压测流量，拦截器不做替换，直接使用业务库连接"
        ),
    }


# ==================== 压测开关控制 ====================

class SwitchControl(BaseModel):
    enabled: bool


@app.post("/switch/cluster_test")
def control_cluster_test(control: SwitchControl):
    """
    控制全局压测开关 (Gate 1)

    模拟控制台远程下发压测指令。
    开启后，即使没有 x-pressure-test Header，
    后续请求的 Gate 1 也会通过。
    """
    if control.enabled:
        PradarSwitcher.turn_cluster_test_switch_on()
    else:
        PradarSwitcher.turn_cluster_test_switch_off()

    return {
        "cluster_test_switch": PradarSwitcher.is_cluster_test_enabled(),
        "set_to": control.enabled,
    }


# ==================== 启动 ====================

def _register_demo_shadow_config():
    """注册演示用影子库配置到 ShadowConfigCenter"""
    config = ShadowDatabaseConfig(
        ds_type=0,
        url=BUSINESS_JDBC_URL,
        username=BUSINESS_DB["user"],
        password=BUSINESS_DB["password"],
        shadow_url=f"jdbc:mysql://localhost:3306/pt_wefire_db_sit",
        shadow_username=SHADOW_DB["user"],
        shadow_password=SHADOW_DB["password"],
    )
    get_config_center().register_db_config(config)
    logger.info(f"演示影子库配置已注册: wefire_db_sit → pt_wefire_db_sit")


def print_startup_info():
    print("=" * 60)
    print("PyLinkAgent Demo v3.0 — 真实 MySQL 影子路由")
    print("=" * 60)
    print()
    print("业务库: wefire_db_sit (root@localhost:3306)")
    print("影子库: pt_wefire_db_sit (root@localhost:3306)")
    print()
    print("核心功能: Pradar 两门路由 + 真实 MySQL 查询")
    print("  Gate 1: PradarSwitcher (全局压测开关)")
    print("  Gate 2: Pradar.set_cluster_test (流量染色)")
    print()
    print("端点:")
    print("  GET  /                  - 首页")
    print("  GET  /health            - 健康检查 + DB 连通性")
    print("  GET  /api/users         - 用户列表 (真实 MySQL)")
    print("  GET  /api/orders        - 订单列表")
    print("  GET  /api/products      - 商品列表")
    print("  GET  /api/chain/{id}    - 链路调用 (跨表)")
    print("  GET  /api/sql/rewrite   - SQL 重写")
    print("  GET  /db/query?sql=...  - 执行任意 SQL")
    print("  GET  /routing/decision  - 两门决策详情")
    print("  GET  /routing/mysql     - ShadowRouter 连接参数")
    print("  POST /switch/cluster_test - 压测开关控制")
    print("  GET  /shadow/status     - 影子状态")
    print()
    print("测试命令:")
    print("  # 正常流量 — 业务库 (wefire_db_sit)")
    print("  curl http://localhost:8000/api/users | python -m json.tool")
    print()
    print("  # 压测流量 — 影子库 (pt_wefire_db_sit)")
    print('  curl -H "x-pressure-test: true" http://localhost:8000/api/users | python -m json.tool')
    print()
    print("  # 任意 SQL (压测)")
    print('  curl -H "x-pressure-test: true" "http://localhost:8000/db/query?sql=SELECT * FROM users" | python -m json.tool')
    print()
    print("  # 两门决策详情 (压测)")
    print('  curl -H "x-pressure-test: true" http://localhost:8000/routing/decision | python -m json.tool')
    print("=" * 60)


if __name__ == "__main__":
    import uvicorn
    print_startup_info()
    _register_demo_shadow_config()
    uvicorn.run(app, host="0.0.0.0", port=8000)
