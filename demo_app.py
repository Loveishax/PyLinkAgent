"""
PyLinkAgent Demo Application - 影子路由全链路演示

演示 PyLinkAgent 两门影子路由决策:
  Gate 1: PradarSwitcher.is_cluster_test_enabled() - 全局压测开关
  Gate 2: Pradar.is_cluster_test()               - 当前请求流量染色

数据流:
  HTTP Header (x-pressure-test)
    -> Middleware 检测压测 Header
    -> PradarSwitcher.turn_cluster_test_switch_on()   [Gate 1]
    -> Pradar.start_trace() + Pradar.set_cluster_test(True)  [Gate 2]
    -> ShadowRouter.should_route() = Gate1 && Gate2
    -> 路由到业务数据 or 影子数据
    -> Pradar.end_trace() 清理
"""

import os
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time
import logging

# ==================== PyLinkAgent 影子路由模块 ====================

from pylinkagent.pradar import Pradar, PradarSwitcher
from pylinkagent.shadow import (
    get_router, get_config_center, get_shadow_context,
    ShadowDatabaseConfig, ShadowSQLRewriter,
)

# ==================== 模拟数据库 ====================

USERS_DB = [
    {"id": 1, "name": "张三", "email": "zhangsan@example.com"},
    {"id": 2, "name": "李四", "email": "lisi@example.com"},
    {"id": 3, "name": "王五", "email": "wangwu@example.com"},
]

SHADOW_USERS_DB = [
    {"id": 1, "name": "影子用户 张三", "email": "pt_zhangsan@test.com", "is_shadow": True},
    {"id": 2, "name": "影子用户 李四", "email": "pt_lisi@test.com", "is_shadow": True},
    {"id": 3, "name": "影子用户 王五", "email": "pt_wangwu@test.com", "is_shadow": True},
]

ORDERS_DB = [
    {"id": 101, "user_id": 1, "amount": 99.99, "status": "已支付"},
    {"id": 102, "user_id": 2, "amount": 199.99, "status": "待发货"},
]

SHADOW_ORDERS_DB = [
    {"id": 101, "user_id": 1, "amount": 999.99, "status": "影子已支付", "is_shadow": True},
    {"id": 102, "user_id": 2, "amount": 1999.99, "status": "影子待发货", "is_shadow": True},
]

PRODUCTS_DB = [
    {"id": 1, "name": "iPhone 15", "price": 7999},
    {"id": 2, "name": "MacBook Pro", "price": 14999},
]

SHADOW_PRODUCTS_DB = [
    {"id": 1, "name": "影子 iPhone 15", "price": 9999, "is_shadow": True},
    {"id": 2, "name": "影子 MacBook Pro", "price": 19999, "is_shadow": True},
]

# ==================== 应用 ====================

app = FastAPI(
    title="PyLinkAgent Demo",
    description="影子路由全链路演示 (Pradar + ShadowRouter)",
    version="2.0",
)

logger = logging.getLogger(__name__)


# ==================== 影子路由中间件 ====================

@app.middleware("http")
async def shadow_routing_middleware(request: Request, call_next):
    """
    影子路由中间件 — 核心两门决策

    每个请求经过此中间件:
    1. 检测 x-pressure-test Header
    2. 打开全局压测开关 (Gate 1)
    3. 创建 Pradar Trace 并标记压测 (Gate 2)
    4. ShadowRouter.should_route() 做路由决策
    5. 将路由结果存入 request.state
    6. 请求结束后清理 Pradar 上下文
    """
    # 提取压测 Header
    is_pressure = (
        request.headers.get("x-pressure-test", "").lower() == "true"
        or request.headers.get("x-shadow-flag") is not None
    )

    routing_info = {
        "is_pressure_header": is_pressure,
        "gate1_global_switch": False,
        "gate2_traffic_dye": False,
        "should_route": False,
        "target": "business",
        "trace_id": "",
    }

    try:
        if is_pressure:
            # Gate 1: 打开全局压测开关
            PradarSwitcher.turn_cluster_test_switch_on()
            routing_info["gate1_global_switch"] = True

            # Gate 2: 创建 Trace 并标记为压测流量
            ctx = Pradar.start_trace("demo-app", "web", request.url.path)
            Pradar.set_cluster_test(True)
            routing_info["gate2_traffic_dye"] = True
            routing_info["trace_id"] = ctx.trace_id

            # Pradar 用户数据透传
            Pradar.set_user_data("source", "demo_middleware")

        # 两门决策: ShadowRouter.should_route()
        router = get_router()
        should_route = router.should_route()
        routing_info["should_route"] = should_route
        routing_info["target"] = "shadow" if should_route else "business"

        # ShadowRouter.route_mysql() 生成真实影子连接参数
        # 必须在 Pradar 上下文中调用 (should_route 依赖 is_cluster_test)
        if should_route:
            business_url = "jdbc:mysql://7.198.147.127:3306/wefire_db_sit"
            shadow_conn = router.route_mysql(
                original_url=business_url,
                original_username="wefireSitAdmin",
            )
            if shadow_conn and "host" in shadow_conn:
                routing_info["shadow_mysql"] = {
                    "host": shadow_conn.get("host"),
                    "port": shadow_conn.get("port"),
                    "database": shadow_conn.get("database"),
                    "user": shadow_conn.get("user"),
                }

        # 存入 request.state 供业务端点使用
        request.state.routing = routing_info

        response = await call_next(request)
        return response

    finally:
        # 清理 Pradar 上下文 (仅压测请求有)
        if Pradar.has_context():
            Pradar.end_trace()

        # 如果当前请求没有压力但全局开关开着，保留开关状态
        # 这样后续没有 Header 的请求也能被路由到影子库
        # (实际场景中，全局开关由控制台远程控制)


# ==================== 路由辅助函数 ====================

def route_data(business_data, shadow_data, request: Request):
    """
    根据路由决策返回数据

    从 request.state.routing 读取中间件决策结果
    """
    routing = getattr(request.state, "routing", {})
    is_shadow = routing.get("should_route", False)
    data = shadow_data if is_shadow else business_data
    return {
        "data": data,
        "routing": {
            "target": "shadow" if is_shadow else "business",
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
<!DOCTYPE html><html><head><title>PyLinkAgent Demo</title>
<style>body{font-family:monospace;margin:40px;background:#1a1a2e;color:#e0e0e0}
.container{max-width:800px;margin:0 auto}
h1{color:#00d4ff}h2{color:#7b68ee;margin-top:30px}
.endpoint{background:#16213e;padding:12px;margin:8px 0;border-radius:4px;border-left:3px solid #00d4ff}
.method{color:#00d4ff;font-weight:bold}
code{background:#0f3460;padding:2px 8px;border-radius:3px}
.pressure{background:#1a1a3e;border-left-color:#ff6b6b}
.info{background:#0f3460;padding:15px;margin-top:15px;border-radius:4px}
</style></head><body><div class="container">
<h1>PyLinkAgent Demo</h1><p>影子路由全链路演示</p>
<h2>API 端点</h2>
<div class="endpoint"><span class="method">GET</span> <code>/health</code> 健康检查</div>
<div class="endpoint"><span class="method">GET</span> <code>/api/users</code> 用户列表</div>
<div class="endpoint"><span class="method">GET</span> <code>/api/orders</code> 订单列表</div>
<div class="endpoint"><span class="method">GET</span> <code>/api/products</code> 商品列表</div>
<div class="endpoint"><span class="method">GET</span> <code>/api/chain/{user_id}</code> 链路调用</div>
<div class="endpoint pressure"><span class="method">GET</span> <code>/api/sql/rewrite?sql=...</code> SQL 重写</div>
<div class="endpoint pressure"><span class="method">POST</span> <code>/shadow/config</code> 注册影子配置</div>
<div class="endpoint"><span class="method">GET</span> <code>/shadow/status</code> 影子状态</div>
<div class="endpoint"><span class="method">GET</span> <code>/routing/decision</code> 两门决策详情</div>
<div class="endpoint pressure"><span class="method">POST</span> <code>/switch/cluster_test</code> 压测开关控制</div>
<div class="info">
<h3>压测流量标识</h3>
<p><code>curl http://localhost:8000/api/users</code> — 正常流量</p>
<p><code>curl -H "x-pressure-test: true" http://localhost:8000/api/users</code> — 压测流量</p>
</div></div></body></html>
"""


@app.get("/health")
def health():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "pylinkagent-demo-v2",
        "cluster_test_switch": PradarSwitcher.is_cluster_test_enabled(),
    }


@app.get("/api/users")
def list_users(request: Request):
    """用户列表 — 路由决策由中间件完成"""
    return route_data(USERS_DB, SHADOW_USERS_DB, request)


@app.get("/api/users/{user_id}")
def get_user(user_id: int, request: Request):
    """用户详情"""
    result = route_data(USERS_DB, SHADOW_USERS_DB, request)
    for user in result["data"]:
        if user["id"] == user_id:
            return {"data": [user], "routing": result["routing"]}
    raise HTTPException(404, "User not found")


@app.get("/api/orders")
def list_orders(request: Request):
    """订单列表"""
    return route_data(ORDERS_DB, SHADOW_ORDERS_DB, request)


@app.get("/api/products")
def list_products(request: Request):
    """商品列表"""
    return route_data(PRODUCTS_DB, SHADOW_PRODUCTS_DB, request)


# ==================== 链路调用演示 ====================

@app.get("/api/chain/{user_id}")
def chain_call(user_id: int, request: Request):
    """
    链路调用演示

    在一次请求中查询用户 + 订单，展示影子路由的一致性
    """
    routing = getattr(request.state, "routing", {})
    is_shadow = routing.get("should_route", False)

    users = SHADOW_USERS_DB if is_shadow else USERS_DB
    orders = SHADOW_ORDERS_DB if is_shadow else ORDERS_DB

    user = next((u for u in users if u["id"] == user_id), None)
    user_orders = [o for o in orders if o["user_id"] == user_id]

    return {
        "user": user,
        "orders": user_orders,
        "routing": {
            "target": "shadow" if is_shadow else "business",
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

    使用 ShadowSQLRewriter 将业务表名替换为影子表名
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
    """
    两门决策详情

    展示当前请求经过两门决策的完整信息:
    - Gate 1: PradarSwitcher 全局开关状态
    - Gate 2: Pradar 当前请求压测标记
    - Result: ShadowRouter.should_route() = Gate1 && Gate2
    """
    routing = getattr(getattr(request, "state", None), "routing", {})

    # 额外获取 Pradar 上下文信息
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
        "how_to_test": {
            "business": "curl http://localhost:8000/routing/decision",
            "shadow": 'curl -H "x-pressure-test: true" http://localhost:8000/routing/decision',
        },
    }


# ==================== 影子连接参数演示 ====================

@app.get("/routing/mysql")
def route_mysql_demo(
    request: Request = None,
    x_pressure_test: Optional[str] = Header(None),
):
    """
    演示 ShadowRouter.route_mysql() 真实生成影子连接参数

    生产环境中，wrapt 拦截器会:
    1. 拦截 pymysql.connect(host='7.198.147.127', port=3306, db='wefire_db_sit')
    2. 调用 ShadowRouter.route_mysql() 获取影子连接参数
    3. 替换为 ShadowRouter 返回的影子库 host/user/db
    """
    routing = getattr(getattr(request, "state", None), "routing", {})
    shadow_mysql = routing.get("shadow_mysql")

    # 模拟业务库连接参数 (对应真实 API 中的 wefire_db_sit)
    business_url = "jdbc:mysql://7.198.147.127:3306/wefire_db_sit"
    business_user = "wefireSitAdmin"

    result = {
        "routing_decision": routing,
        "business_connection": {
            "url": business_url,
            "pymysql_url": ShadowDatabaseConfig.jdbc_to_pymysql(business_url),
            "username": business_user,
        },
    }

    if shadow_mysql:
        result["shadow_connection"] = {
            "generated_by": "ShadowRouter.route_mysql() (in middleware)",
            "host": shadow_mysql.get("host"),
            "port": shadow_mysql.get("port"),
            "database": shadow_mysql.get("database"),
            "user": shadow_mysql.get("user"),
            "pymysql_url": f"mysql+pymysql://{shadow_mysql.get('user')}@{shadow_mysql.get('host')}:{shadow_mysql.get('port')}/{shadow_mysql.get('database')}",
        }
        result["interceptor_behavior"] = (
            f"pymysql.connect(host='7.198.147.127') "
            f"→ 拦截替换 → "
            f"connect(host={shadow_mysql.get('host')}, "
            f"user={shadow_mysql.get('user')}, "
            f"db={shadow_mysql.get('database')})"
        )
    else:
        result["shadow_connection"] = None
        result["interceptor_behavior"] = (
            "无压测流量，拦截器不做替换，直接使用业务库连接"
        )

    return result


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

def print_startup_info():
    print("=" * 60)
    print("PyLinkAgent Demo v2.0 — 影子路由全链路")
    print("=" * 60)
    print()
    print("核心功能: 两门影子路由决策")
    print("  Gate 1: PradarSwitcher (全局压测开关)")
    print("  Gate 2: Pradar.set_cluster_test (流量染色)")
    print()
    print("端点:")
    print("  GET  /                  - 首页")
    print("  GET  /health            - 健康检查")
    print("  GET  /api/users         - 用户列表 (路由决策)")
    print("  GET  /api/orders        - 订单列表 (路由决策)")
    print("  GET  /api/products      - 商品列表 (路由决策)")
    print("  GET  /api/chain/{id}    - 链路调用 (一致性)")
    print("  GET  /api/sql/rewrite   - SQL 重写")
    print("  GET  /routing/decision  - 两门决策详情")
    print("  GET  /routing/mysql     - ShadowRouter.route_mysql() 真实参数")
    print("  POST /switch/cluster_test - 压测开关控制")
    print("  POST /shadow/config     - 注册影子配置")
    print("  GET  /shadow/status     - 影子状态")
    print()
    print("测试命令:")
    print('  # 正常流量 (路由到业务库)')
    print('  curl http://localhost:8000/api/users')
    print()
    print('  # 压测流量 (路由到影子库)')
    print('  curl -H "x-pressure-test: true" http://localhost:8000/api/users')
    print()
    print('  # 查看两门决策详情')
    print('  curl -H "x-pressure-test: true" http://localhost:8000/routing/decision')
    print()
    print('  # 查看 ShadowRouter 生成的真实影子连接参数')
    print('  curl -H "x-pressure-test: true" http://localhost:8000/routing/mysql')
    print("=" * 60)


def _register_demo_shadow_config():
    """注册演示用影子库配置 (模拟 ConfigFetcher 从控制台拉取)"""
    config = ShadowDatabaseConfig(
        ds_type=0,
        url="jdbc:mysql://7.198.147.127:3306/wefire_db_sit",
        username="wefireSitAdmin",
        shadow_url="jdbc:mysql://7.198.147.127:3306/pt_wefire_db_sit",
        shadow_username="drpAdmin",
        shadow_password="Flzx3qc###",
    )
    get_config_center().register_db_config(config)
    logger.info("演示影子库配置已注册: wefire_db_sit → pt_wefire_db_sit")


if __name__ == "__main__":
    import uvicorn
    print_startup_info()
    _register_demo_shadow_config()
    uvicorn.run(app, host="0.0.0.0", port=8000)
