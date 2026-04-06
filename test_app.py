"""
PyLinkAgent 测试应用

这是一个完整的 FastAPI 应用，用于测试 PyLinkAgent 的各项功能：
- FastAPI 框架插桩
- requests 客户端插桩
- Trace 上下文传递
- 数据采集
"""

from fastapi import FastAPI, HTTPException
import requests
import time
from typing import Dict, Any

app = FastAPI(
    title="PyLinkAgent Test App",
    description="用于测试 PyLinkAgent 探针功能",
    version="1.0.0"
)

# ============= 健康检查接口 =============

@app.get("/health")
def health_check():
    """健康检查接口（应该被忽略）"""
    return {"status": "healthy"}


# ============= 基础 HTTP 接口 =============

@app.get("/")
def read_root():
    """根路径"""
    return {
        "message": "Welcome to PyLinkAgent Test App",
        "endpoints": [
            "/",
            "/users/{user_id}",
            "/external",
            "/chain",
            "/error",
            "/slow",
            "/health"
        ]
    }


@app.get("/users/{user_id}")
def get_user(user_id: int):
    """获取用户信息"""
    if user_id < 1:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com"
    }


# ============= HTTP 客户端调用接口 =============

@app.get("/external")
def call_external_api():
    """调用外部 HTTP 接口（测试 requests 插桩）"""
    start = time.time()

    # 调用 httpbin 测试接口
    resp = requests.get("https://httpbin.org/get", timeout=10)

    return {
        "status_code": resp.status_code,
        "elapsed_ms": (time.time() - start) * 1000,
        "data": resp.json()
    }


@app.post("/external/post")
def post_to_external_api(data: Dict[str, Any]):
    """POST 请求到外部接口"""
    resp = requests.post(
        "https://httpbin.org/post",
        json=data,
        timeout=10
    )
    return {
        "status_code": resp.status_code,
        "data": resp.json()
    }


# ============= 链路追踪接口 =============

@app.get("/chain")
def chain_call():
    """链路调用（测试 Span 嵌套）"""
    # 模拟业务逻辑
    user_data = _get_user_info(123)
    order_data = _get_order_info(456)

    return {
        "user": user_data,
        "order": order_data
    }


def _get_user_info(user_id: int) -> Dict[str, Any]:
    """内部函数：获取用户信息"""
    time.sleep(0.1)  # 模拟数据库查询
    return {"user_id": user_id, "name": f"User {user_id}"}


def _get_order_info(order_id: int) -> Dict[str, Any]:
    """内部函数：获取订单信息"""
    time.sleep(0.15)  # 模拟数据库查询
    return {"order_id": order_id, "total": 99.99}


# ============= 错误处理接口 =============

@app.get("/error")
def trigger_error():
    """触发错误（测试异常捕获）"""
    raise ValueError("This is a test error for PyLinkAgent")


@app.get("/error/http")
def trigger_http_error():
    """触发 HTTP 错误"""
    raise HTTPException(status_code=500, detail="Internal Server Error")


# ============= 慢接口接口 =============

@app.get("/slow")
def slow_endpoint():
    """慢接口（测试耗时统计）"""
    time.sleep(2)  # 等待 2 秒
    return {"message": "This is a slow response", "slept": 2}


# ============= 数据库模拟接口 =============

@app.get("/db/query")
def simulate_db_query(query: str = "SELECT 1"):
    """模拟数据库查询"""
    start = time.time()

    # 模拟数据库查询延迟
    time.sleep(0.05)

    # 记录 SQL（实际应该被 SQLAlchemy 插桩捕获）
    print(f"Executing SQL: {query}")

    return {
        "query": query,
        "elapsed_ms": (time.time() - start) * 1000,
        "rows": [{"id": 1, "value": "test"}]
    }


# ============= 启动信息 =============

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("PyLinkAgent Test Application")
    print("=" * 60)
    print("Starting server on http://localhost:8000")
    print("")
    print("Available endpoints:")
    print("  GET  /              - 首页")
    print("  GET  /health        - 健康检查")
    print("  GET  /users/{id}    - 获取用户")
    print("  GET  /external      - 调用外部 API")
    print("  POST /external/post - POST 到外部 API")
    print("  GET  /chain         - 链路追踪测试")
    print("  GET  /error         - 触发错误")
    print("  GET  /slow          - 慢接口测试")
    print("  GET  /db/query      - 数据库模拟")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
