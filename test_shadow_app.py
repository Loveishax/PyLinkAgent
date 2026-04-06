"""
PyLinkAgent Shadow Database Test Application

测试应用用于验证影子库功能:
- 正常流量 vs 压测流量
- 影子库路由
- 影子表名映射
- SQLAlchemy 拦截
"""

from fastapi import FastAPI, Request, Header
from typing import Optional, Dict, Any
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PyLinkAgent Shadow DB Test App",
    description="影子库功能测试应用",
    version="1.0.0"
)

# 模拟数据库
USERS_DB = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
    2: {"id": 2, "name": "Bob", "email": "bob@example.com"},
    3: {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
}

ORDERS_DB = {
    101: {"order_id": 101, "user_id": 1, "total": 99.99, "status": "completed"},
    102: {"order_id": 102, "user_id": 2, "total": 199.99, "status": "pending"},
    103: {"order_id": 103, "user_id": 3, "total": 299.99, "status": "shipped"},
}


# ============= 工具函数 =============

def simulate_db_query(query_type: str, data: Dict) -> Dict[str, Any]:
    """
    模拟数据库查询

    Args:
        query_type: 查询类型 (shadow/business)
        data: 查询数据

    Returns:
        查询结果
    """
    start = time.time()

    # 模拟查询延迟
    time.sleep(0.05)

    elapsed = (time.time() - start) * 1000

    return {
        "query_type": query_type,
        "data": data,
        "elapsed_ms": round(elapsed, 2),
        "table": "users" if "user_id" in data or "id" in data else "orders",
    }


def get_user_from_db(user_id: int, use_shadow: bool = False) -> Optional[Dict]:
    """
    从数据库获取用户

    Args:
        user_id: 用户 ID
        use_shadow: 是否使用影子库

    Returns:
        用户数据
    """
    if use_shadow:
        # 影子库查询 - 返回影子数据
        return {
            "id": user_id,
            "name": f"Shadow_User_{user_id}",
            "email": f"shadow_user{user_id}@test.com",
            "is_shadow": True
        }
    else:
        # 业务库查询 - 返回正常数据
        return USERS_DB.get(user_id)


def get_order_from_db(order_id: int, use_shadow: bool = False) -> Optional[Dict]:
    """
    从数据库获取订单

    Args:
        order_id: 订单 ID
        use_shadow: 是否使用影子库

    Returns:
        订单数据
    """
    if use_shadow:
        # 影子库查询 - 返回影子数据
        return {
            "order_id": order_id,
            "user_id": order_id * 10,
            "total": 999.99,
            "status": "shadow_test",
            "is_shadow": True
        }
    else:
        # 业务库查询 - 返回正常数据
        return ORDERS_DB.get(order_id)


# ============= HTTP 接口 =============

@app.get("/")
def read_root():
    """根路径"""
    return {
        "message": "PyLinkAgent Shadow DB Test App",
        "endpoints": [
            "/",
            "/health",
            "/users/{id}",
            "/orders/{id}",
            "/chain/{user_id}",
            "/db/status",
            "/db/config",
        ],
        "shadow_db_enabled": True,
    }


@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy", "shadow_db": "ready"}


@app.get("/users/{user_id}")
def get_user(
    user_id: int,
    request: Request,
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
    x_shadow_flag: Optional[str] = Header(None, alias="x-shadow-flag"),
):
    """
    获取用户信息

    如果是压测流量，路由到影子库
    """
    # 检查是否是压测流量
    is_pressure = (
        x_pressure_test and x_pressure_test.lower() == "true"
    ) or (x_shadow_flag is not None)

    logger.info(f"GET /users/{user_id} - pressure={is_pressure}")

    # 根据流量类型获取数据
    user_data = get_user_from_db(user_id, use_shadow=is_pressure)

    if not user_data:
        return {"error": "User not found", "user_id": user_id}

    return {
        **user_data,
        "is_pressure_test": is_pressure,
        "headers": {
            "x-pressure-test": x_pressure_test,
            "x-shadow-flag": x_shadow_flag,
        }
    }


@app.get("/orders/{order_id}")
def get_order(
    order_id: int,
    request: Request,
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
):
    """
    获取订单信息

    如果是压测流量，路由到影子库
    """
    is_pressure = x_pressure_test and x_pressure_test.lower() == "true"
    logger.info(f"GET /orders/{order_id} - pressure={is_pressure}")

    order_data = get_order_from_db(order_id, use_shadow=is_pressure)

    if not order_data:
        return {"error": "Order not found", "order_id": order_id}

    return {
        **order_data,
        "is_pressure_test": is_pressure,
    }


@app.get("/chain/{user_id}")
def chain_call(
    user_id: int,
    request: Request,
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
):
    """
    链路调用测试

    同时查询用户和订单，验证影子库路由
    """
    is_pressure = x_pressure_test and x_pressure_test.lower() == "true"
    logger.info(f"GET /chain/{user_id} - pressure={is_pressure}")

    # 查询用户
    user_data = get_user_from_db(user_id, use_shadow=is_pressure)

    # 查询订单 (假设用户有一个订单)
    order_id = user_id * 100 + 1
    order_data = get_order_from_db(order_id, use_shadow=is_pressure)

    return {
        "user": user_data,
        "order": order_data,
        "is_pressure_test": is_pressure,
        "routing": {
            "user_table": "shadow_users" if is_pressure else "users",
            "order_table": "shadow_orders" if is_pressure else "orders",
        }
    }


@app.get("/db/status")
def db_status(
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
):
    """
    数据库状态检查

    显示当前流量类型和路由配置
    """
    from pylinkagent.shadow import get_router, get_shadow_context

    is_pressure = x_pressure_test and x_pressure_test.lower() == "true"
    router = get_router()

    # 获取配置信息
    configs = router.config_manager.get_all_configs() if hasattr(router, 'config_manager') else []

    return {
        "is_pressure_test": is_pressure,
        "shadow_routing_enabled": router.is_enabled(),
        "shadow_configs_count": len(configs),
        "shadow_configs": [
            {
                "url": cfg.url,
                "shadow_url": cfg.shadow_url,
                "ds_type": cfg.ds_type,
                "tables": list(cfg.business_shadow_tables.keys()),
            }
            for cfg in configs
        ],
        "context": str(get_shadow_context()),
    }


@app.get("/db/config")
def db_config():
    """
    影子库配置信息
    """
    from pylinkagent.shadow import get_router

    router = get_router()
    configs = router.config_manager.get_all_configs() if hasattr(router, 'config_manager') else []

    return {
        "configs": [
            {
                "ds_type": cfg.ds_type,
                "url": cfg.url,
                "username": cfg.username,
                "shadow_url": cfg.shadow_url,
                "shadow_username": cfg.shadow_username,
                "shadow_account_prefix": cfg.shadow_account_prefix,
                "shadow_account_suffix": cfg.shadow_account_suffix,
                "business_shadow_tables": cfg.business_shadow_tables,
            }
            for cfg in configs
        ]
    }


@app.post("/db/config/register")
async def register_shadow_config(config_data: dict):
    """
    注册影子库配置

    Request Body:
    {
        "ds_type": 0,
        "url": "jdbc:mysql://localhost:3306/test",
        "username": "root",
        "password": "password",
        "shadow_url": "jdbc:mysql://localhost:3306/shadow_test",
        "shadow_username": "PT_root",
        "shadow_password": "PT_password",
        "business_shadow_tables": {
            "users": "shadow_users",
            "orders": "shadow_orders"
        }
    }
    """
    from pylinkagent.shadow import get_router, ShadowDatabaseConfig

    router = get_router()

    try:
        config = ShadowDatabaseConfig(
            ds_type=config_data.get("ds_type", 0),
            url=config_data.get("url", ""),
            username=config_data.get("username", ""),
            password=config_data.get("password", ""),
            shadow_url=config_data.get("shadow_url", ""),
            shadow_username=config_data.get("shadow_username"),
            shadow_password=config_data.get("shadow_password"),
            shadow_account_prefix=config_data.get("shadow_account_prefix", "PT_"),
            shadow_account_suffix=config_data.get("shadow_account_suffix", ""),
            business_shadow_tables=config_data.get("business_shadow_tables", {}),
        )

        router.register_config(config)

        return {
            "status": "success",
            "message": "Shadow config registered",
            "config": str(config),
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@app.get("/sql/rewrite")
def test_sql_rewrite(
    sql: str = "SELECT * FROM users WHERE id = 1",
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
):
    """
    测试 SQL 重写

    压测流量下，表名会被替换为影子表名
    """
    from pylinkagent.shadow import get_router, get_shadow_context, create_new_context

    is_pressure = x_pressure_test and x_pressure_test.lower() == "true"

    # 设置压测上下文
    if is_pressure:
        ctx = create_new_context(is_pressure=True)

    router = get_router()
    rewritten_sql = router.rewrite_sql(sql, "jdbc:mysql://localhost:3306/test", "root")

    return {
        "original_sql": sql,
        "rewritten_sql": rewritten_sql,
        "is_pressure_test": is_pressure,
        "shadow_tables": list(router.config_manager.get_all_configs()[0].business_shadow_tables.items())
        if router.config_manager.get_all_configs() else []
    }


# ============= 启动信息 =============

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("PyLinkAgent Shadow DB Test Application")
    print("=" * 60)
    print("")
    print("Available endpoints:")
    print("  GET  /                  - 首页")
    print("  GET  /health            - 健康检查")
    print("  GET  /users/{id}        - 获取用户 (支持影子库)")
    print("  GET  /orders/{id}       - 获取订单 (支持影子库)")
    print("  GET  /chain/{id}        - 链路调用测试")
    print("  GET  /db/status         - 数据库状态")
    print("  GET  /db/config         - 影子库配置")
    print("  POST /db/config/register - 注册影子库配置")
    print("  GET  /sql/rewrite       - SQL 重写测试")
    print("")
    print("Pressure test headers:")
    print("  x-pressure-test: true  - 标记为压测流量")
    print("  x-shadow-flag: <value> - 影子标记")
    print("")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)
