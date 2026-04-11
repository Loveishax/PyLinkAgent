"""
PyLinkAgent Demo Application - 简化版
用于压测流量路由验证
"""

from fastapi import FastAPI, Header
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="PyLinkAgent Demo", version="1.0.0")

# 模拟数据库
USERS_DB = [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "is_shadow": False},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "is_shadow": False}
]

SHADOW_USERS_DB = [
    {"id": 1, "name": "Shadow Alice", "email": "shadow_alice@example.com", "is_shadow": True},
    {"id": 2, "name": "Shadow Bob", "email": "shadow_bob@example.com", "is_shadow": True}
]

ORDERS_DB = [
    {"id": 101, "user_id": 1, "product": "Laptop", "is_shadow": False},
    {"id": 102, "user_id": 2, "product": "Phone", "is_shadow": False}
]

SHADOW_ORDERS_DB = [
    {"id": 101, "user_id": 1, "product": "Shadow Laptop", "is_shadow": True},
    {"id": 102, "user_id": 2, "product": "Shadow Phone", "is_shadow": True}
]


def is_pressure_test(
    x_pressure_test: Optional[str] = Header(None),
    x_shadow_flag: Optional[str] = Header(None),
    x_pradar_trace: Optional[str] = Header(None)
) -> bool:
    """判断是否为压测流量"""
    return (
        x_pressure_test == "true" or
        x_shadow_flag is not None or
        x_pradar_trace == "pressure-test"
    )


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "pylinkagent-demo"}


@app.get("/api/users")
async def get_users(pressure: bool = None):
    """获取用户列表"""
    if pressure is None:
        pressure = False
    return SHADOW_USERS_DB if pressure else USERS_DB


@app.get("/api/users/{user_id}")
async def get_user(user_id: int, pressure: bool = None):
    """获取用户详情"""
    if pressure is None:
        pressure = False
    db = SHADOW_USERS_DB if pressure else USERS_DB
    for user in db:
        if user["id"] == user_id:
            return user
    return {"error": "User not found"}


@app.get("/api/orders")
async def get_orders(pressure: bool = None):
    """获取订单列表"""
    if pressure is None:
        pressure = False
    return SHADOW_ORDERS_DB if pressure else ORDERS_DB


@app.get("/")
async def index():
    """首页"""
    return {
        "service": "PyLinkAgent Demo Application",
        "version": "1.0.0",
        "endpoints": [
            "GET /health - Health Check",
            "GET /api/users - User List",
            "GET /api/users/{id} - User Details",
            "GET /api/orders - Order List"
        ],
        "pressure_test_header": "x-pressure-test: true"
    }


# 带 Header 检测的路由
@app.get("/api/users-with-header")
async def get_users_with_header(
    x_pressure_test: Optional[str] = Header(None),
    x_shadow_flag: Optional[str] = Header(None),
    x_pradar_trace: Optional[str] = Header(None)
):
    """获取用户列表（自动检测压测流量）"""
    pressure = is_pressure_test(x_pressure_test, x_shadow_flag, x_pradar_trace)
    logger.info(f"收到请求，pressure={pressure}, headers: x_pressure_test={x_pressure_test}, x_shadow_flag={x_shadow_flag}, x_pradar_trace={x_pradar_trace}")
    return SHADOW_USERS_DB if pressure else USERS_DB


@app.get("/api/orders-with-header")
async def get_orders_with_header(
    x_pressure_test: Optional[str] = Header(None),
    x_shadow_flag: Optional[str] = Header(None),
    x_pradar_trace: Optional[str] = Header(None)
):
    """获取订单列表（自动检测压测流量）"""
    pressure = is_pressure_test(x_pressure_test, x_shadow_flag, x_pradar_trace)
    logger.info(f"收到请求，pressure={pressure}")
    return SHADOW_ORDERS_DB if pressure else ORDERS_DB


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("PyLinkAgent Demo Application")
    print("=" * 60)
    print("")
    print("Endpoints:")
    print("  GET  /health                - Health Check")
    print("  GET  /                      - Application Info")
    print("  GET  /api/users             - User List")
    print("  GET  /api/users/{id}        - User Details")
    print("  GET  /api/orders            - Order List")
    print("  GET  /api/users-with-header - User List (auto-detect pressure)")
    print("  GET  /api/orders-with-header - Order List (auto-detect pressure)")
    print("")
    print("Test Commands:")
    print("  # Normal traffic")
    print('  curl http://localhost:8000/api/users')
    print("")
    print("  # Pressure traffic")
    print('  curl http://localhost:8000/api/users/with-header -H "x-pressure-test: true"')
    print("")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
