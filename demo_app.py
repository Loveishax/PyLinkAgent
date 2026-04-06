"""
PyLinkAgent Demo Application

完整的全链路压测演示应用，包含：
- 用户管理
- 订单管理
- 商品管理
- 链路追踪
- SQL 重写演示

支持影子库路由，通过 x-pressure-test Header 标识压测流量
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time
import logging
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PyLinkAgent Demo Application",
    description="全链路压测影子库功能演示应用",
    version="1.0.0"
)

# ============= 模拟数据库 =============

USERS_DB = [
    {"id": 1, "name": "张三", "email": "zhangsan@example.com"},
    {"id": 2, "name": "李四", "email": "lisi@example.com"},
    {"id": 3, "name": "王五", "email": "wangwu@example.com"},
    {"id": 4, "name": "赵六", "email": "zhaoliu@example.com"},
    {"id": 5, "name": "钱七", "email": "qianqi@example.com"},
]

SHADOW_USERS_DB = [
    {"id": 1, "name": "影子用户 1", "email": "shadow_user1@test.com", "is_shadow": True},
    {"id": 2, "name": "影子用户 2", "email": "shadow_user2@test.com", "is_shadow": True},
    {"id": 3, "name": "影子用户 3", "email": "shadow_user3@test.com", "is_shadow": True},
    {"id": 4, "name": "影子用户 4", "email": "shadow_user4@test.com", "is_shadow": True},
    {"id": 5, "name": "影子用户 5", "email": "shadow_user5@test.com", "is_shadow": True},
]

ORDERS_DB = [
    {"id": 1, "user_id": 1, "total": 99.99, "status": "completed"},
    {"id": 2, "user_id": 1, "total": 199.99, "status": "pending"},
    {"id": 3, "user_id": 2, "total": 299.99, "status": "shipped"},
    {"id": 4, "user_id": 3, "total": 399.99, "status": "completed"},
    {"id": 5, "user_id": 4, "total": 499.99, "status": "pending"},
]

SHADOW_ORDERS_DB = [
    {"id": 1, "user_id": 1, "total": 999.99, "status": "shadow_completed", "is_shadow": True},
    {"id": 2, "user_id": 1, "total": 1999.99, "status": "shadow_pending", "is_shadow": True},
    {"id": 3, "user_id": 2, "total": 2999.99, "status": "shadow_shipped", "is_shadow": True},
    {"id": 4, "user_id": 3, "total": 3999.99, "status": "shadow_completed", "is_shadow": True},
    {"id": 5, "user_id": 4, "total": 4999.99, "status": "shadow_pending", "is_shadow": True},
]

PRODUCTS_DB = [
    {"id": 1, "name": "iPhone 15 Pro", "price": 7999.00, "stock": 100},
    {"id": 2, "name": "MacBook Pro 14", "price": 14999.00, "stock": 50},
    {"id": 3, "name": "AirPods Pro", "price": 1899.00, "stock": 200},
    {"id": 4, "name": "iPad Air", "price": 4799.00, "stock": 80},
    {"id": 5, "name": "Apple Watch", "price": 3199.00, "stock": 150},
]

SHADOW_PRODUCTS_DB = [
    {"id": 1, "name": "影子 iPhone 15 Pro", "price": 9999.00, "stock": 10, "is_shadow": True},
    {"id": 2, "name": "影子 MacBook Pro 14", "price": 19999.00, "stock": 5, "is_shadow": True},
    {"id": 3, "name": "影子 AirPods Pro", "price": 2899.00, "stock": 20, "is_shadow": True},
    {"id": 4, "name": "影子 iPad Air", "price": 6799.00, "stock": 8, "is_shadow": True},
    {"id": 5, "name": "影子 Apple Watch", "price": 4199.00, "stock": 15, "is_shadow": True},
]


# ============= 数据模型 =============

class User(BaseModel):
    id: int
    name: str
    email: str
    is_shadow: Optional[bool] = False


class Order(BaseModel):
    id: int
    user_id: int
    total: float
    status: str
    is_shadow: Optional[bool] = False


class Product(BaseModel):
    id: int
    name: str
    price: float
    stock: int
    is_shadow: Optional[bool] = False


# ============= 工具函数 =============

def is_pressure_test(x_pressure_test: Optional[str] = None, x_shadow_flag: Optional[str] = None) -> bool:
    """判断是否为压测流量"""
    return (x_pressure_test and x_pressure_test.lower() == "true") or (x_shadow_flag is not None)


def get_users(pressure: bool) -> List[Dict]:
    """获取用户列表"""
    return SHADOW_USERS_DB if pressure else USERS_DB


def get_orders(pressure: bool) -> List[Dict]:
    """获取订单列表"""
    return SHADOW_ORDERS_DB if pressure else ORDERS_DB


def get_products(pressure: bool) -> List[Dict]:
    """获取商品列表"""
    return SHADOW_PRODUCTS_DB if pressure else PRODUCTS_DB


# ============= HTML 首页 =============

@app.get("/", response_class=HTMLResponse, tags=["首页"])
def read_root():
    """应用首页 - 展示所有 API 端点"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>PyLinkAgent Demo</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 4px; border-left: 4px solid #007bff; }
        .method { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; margin-right: 10px; }
        .get { background: #28a745; color: white; }
        .post { background: #007bff; color: white; }
        code { background: #e9ecef; padding: 2px 6px; border-radius: 3px; font-size: 14px; }
        .pressure-test { background: #fff3cd; border-left-color: #ffc107; }
        .info { color: #666; font-size: 14px; margin-top: 20px; padding: 15px; background: #e7f3ff; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 PyLinkAgent Demo Application</h1>
        <p>全链路压测影子库功能演示应用</p>

        <h2>📋 API 端点</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/health</code>
            <p>健康检查接口</p>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/users</code>
            <p>获取用户列表（压测流量返回影子用户）</p>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/users/{id}</code>
            <p>获取用户详情</p>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/orders</code>
            <p>获取订单列表（压测流量返回影子订单）</p>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/orders/{id}</code>
            <p>获取订单详情</p>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/products</code>
            <p>获取商品列表（压测流量返回影子商品）</p>
        </div>

        <div class="endpoint pressure-test">
            <span class="method get">GET</span>
            <code>/api/chain/{user_id}</code>
            <p>链路调用演示 - 同时查询用户和订单</p>
        </div>

        <div class="endpoint pressure-test">
            <span class="method get">GET</span>
            <code>/api/sql/rewrite?sql=SELECT * FROM users</code>
            <p>SQL 重写演示 - 压测流量下替换表名</p>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <code>/shadow/config</code>
            <p>注册影子库配置</p>
        </div>

        <h2>🔧 压测流量标识</h2>
        <p>在请求中添加 Header 来标识压测流量：</p>
        <code>x-pressure-test: true</code>

        <div class="info">
            <h3>📖 使用示例</h3>
            <p><strong>正常流量：</strong></p>
            <code>curl http://localhost:8000/api/users/1</code>
            <p><strong>压测流量：</strong></p>
            <code>curl -H "x-pressure-test: true" http://localhost:8000/api/users/1</code>
        </div>

        <div class="info">
            <h3>📊 影子库表映射</h3>
            <p><code>users → shadow_users</code></p>
            <p><code>orders → shadow_orders</code></p>
            <p><code>products → shadow_products</code></p>
        </div>
    </div>
</body>
</html>
""")


@app.get("/health", tags=["健康检查"])
def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "pylinkagent-demo",
        "shadow_db_support": True
    }


# ============= 用户接口 =============

@app.get("/api/users", response_model=List[User], tags=["用户管理"])
def list_users(
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
    x_shadow_flag: Optional[str] = Header(None, alias="x-shadow-flag")
):
    """获取用户列表"""
    pressure = is_pressure_test(x_pressure_test, x_shadow_flag)
    logger.info(f"GET /api/users - pressure={pressure}")

    users = get_users(pressure)
    return users


@app.get("/api/users/{user_id}", response_model=User, tags=["用户管理"])
def get_user(
    user_id: int,
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
    x_shadow_flag: Optional[str] = Header(None, alias="x-shadow-flag")
):
    """获取用户详情"""
    pressure = is_pressure_test(x_pressure_test, x_shadow_flag)
    logger.info(f"GET /api/users/{user_id} - pressure={pressure}")

    users = get_users(pressure)
    for user in users:
        if user["id"] == user_id:
            return user

    raise HTTPException(status_code=404, detail="User not found")


# ============= 订单接口 =============

@app.get("/api/orders", response_model=List[Order], tags=["订单管理"])
def list_orders(
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
    x_shadow_flag: Optional[str] = Header(None, alias="x-shadow-flag")
):
    """获取订单列表"""
    pressure = is_pressure_test(x_pressure_test, x_shadow_flag)
    logger.info(f"GET /api/orders - pressure={pressure}")

    orders = get_orders(pressure)
    return orders


@app.get("/api/orders/{order_id}", response_model=Order, tags=["订单管理"])
def get_order(
    order_id: int,
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
    x_shadow_flag: Optional[str] = Header(None, alias="x-shadow-flag")
):
    """获取订单详情"""
    pressure = is_pressure_test(x_pressure_test, x_shadow_flag)
    logger.info(f"GET /api/orders/{order_id} - pressure={pressure}")

    orders = get_orders(pressure)
    for order in orders:
        if order["id"] == order_id:
            return order

    raise HTTPException(status_code=404, detail="Order not found")


# ============= 商品接口 =============

@app.get("/api/products", response_model=List[Product], tags=["商品管理"])
def list_products(
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
    x_shadow_flag: Optional[str] = Header(None, alias="x-shadow-flag")
):
    """获取商品列表"""
    pressure = is_pressure_test(x_pressure_test, x_shadow_flag)
    logger.info(f"GET /api/products - pressure={pressure}")

    products = get_products(pressure)
    return products


@app.get("/api/products/{product_id}", response_model=Product, tags=["商品管理"])
def get_product(
    product_id: int,
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
    x_shadow_flag: Optional[str] = Header(None, alias="x-shadow-flag")
):
    """获取商品详情"""
    pressure = is_pressure_test(x_pressure_test, x_shadow_flag)
    logger.info(f"GET /api/products/{product_id} - pressure={pressure}")

    products = get_products(pressure)
    for product in products:
        if product["id"] == product_id:
            return product

    raise HTTPException(status_code=404, detail="Product not found")


# ============= 链路调用 =============

@app.get("/api/chain/{user_id}", tags=["链路追踪"])
def chain_call(
    user_id: int,
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
    x_shadow_flag: Optional[str] = Header(None, alias="x-shadow-flag")
):
    """
    链路调用演示

    同时查询用户和订单，展示影子库路由效果
    """
    pressure = is_pressure_test(x_pressure_test, x_shadow_flag)
    logger.info(f"GET /api/chain/{user_id} - pressure={pressure}")

    # 查询用户
    users = get_users(pressure)
    user_data = next((u for u in users if u["id"] == user_id), None)

    # 查询订单 (假设用户有订单)
    orders = get_orders(pressure)
    user_orders = [o for o in orders if o["user_id"] == user_id]

    return {
        "user": user_data,
        "orders": user_orders,
        "is_pressure_test": pressure,
        "routing": {
            "user_table": "shadow_users" if pressure else "users",
            "order_table": "shadow_orders" if pressure else "orders",
        }
    }


# ============= SQL 重写演示 =============

@app.get("/api/sql/rewrite", tags=["SQL 重写"])
def sql_rewrite(
    sql: str = "SELECT * FROM users",
    x_pressure_test: Optional[str] = Header(None, alias="x-pressure-test"),
    x_shadow_flag: Optional[str] = Header(None, alias="x-shadow-flag")
):
    """
    SQL 重写演示

    压测流量下，SQL 中的表名会被自动替换为影子表名
    """
    from pylinkagent.shadow import get_router

    pressure = is_pressure_test(x_pressure_test, x_shadow_flag)

    # 设置压测上下文
    if pressure:
        from pylinkagent.shadow.context import create_new_context
        create_new_context(is_pressure=True)

    router = get_router()

    # 模拟 SQL 重写
    original_sql = sql
    rewritten_sql = sql

    # 简单的表名替换演示
    table_mappings = {
        "users": "shadow_users",
        "orders": "shadow_orders",
        "products": "shadow_products",
    }

    if pressure:
        for biz_table, shadow_table in table_mappings.items():
            rewritten_sql = rewritten_sql.replace(biz_table, shadow_table)

    return {
        "original_sql": original_sql,
        "rewritten_sql": rewritten_sql,
        "is_pressure_test": pressure,
        "table_mappings": table_mappings,
    }


# ============= 影子库配置 =============

class ShadowConfig(BaseModel):
    ds_type: int = 0
    url: str
    username: str
    password: Optional[str] = None
    shadow_url: str
    shadow_username: Optional[str] = None
    shadow_password: Optional[str] = None
    shadow_account_prefix: str = "PT_"
    shadow_account_suffix: str = ""
    business_shadow_tables: Dict[str, str] = {}


@app.post("/shadow/config", tags=["配置管理"])
def register_shadow_config(config: ShadowConfig):
    """注册影子库配置"""
    from pylinkagent.shadow import ShadowDatabaseConfig, get_router

    router = get_router()

    shadow_config = ShadowDatabaseConfig(
        ds_type=config.ds_type,
        url=config.url,
        username=config.username,
        password=config.password,
        shadow_url=config.shadow_url,
        shadow_username=config.shadow_username,
        shadow_password=config.shadow_password,
        shadow_account_prefix=config.shadow_account_prefix,
        shadow_account_suffix=config.shadow_account_suffix,
        business_shadow_tables=config.business_shadow_tables,
    )

    router.register_config(shadow_config)

    return {
        "status": "success",
        "message": "Shadow config registered",
        "config": str(shadow_config),
    }


@app.get("/shadow/status", tags=["配置管理"])
def shadow_status():
    """获取影子库状态"""
    from pylinkagent.shadow import get_router, get_shadow_context

    router = get_router()
    configs = router.config_manager.get_all_configs() if hasattr(router, 'config_manager') else []

    return {
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


# ============= 启动信息 =============

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("PyLinkAgent Demo Application")
    print("=" * 60)
    print("")
    print("📋 可用端点:")
    print("  GET  /                  - 应用首页")
    print("  GET  /health            - 健康检查")
    print("  GET  /api/users         - 用户列表")
    print("  GET  /api/users/{id}    - 用户详情")
    print("  GET  /api/orders        - 订单列表")
    print("  GET  /api/orders/{id}   - 订单详情")
    print("  GET  /api/products      - 商品列表")
    print("  GET  /api/chain/{id}    - 链路调用")
    print("  GET  /api/sql/rewrite   - SQL 重写")
    print("  POST /shadow/config     - 注册配置")
    print("  GET  /shadow/status     - 影子库状态")
    print("")
    print("🔧 压测流量标识:")
    print("  x-pressure-test: true  - 标记为压测流量")
    print("  x-shadow-flag: <value> - 影子标记")
    print("")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)
