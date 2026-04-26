import importlib
import os
import sys

import pymysql
from fastapi.testclient import TestClient


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


MYSQL_CONNECT = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "charset": "utf8mb4",
    "autocommit": True,
}


def _count_rows(database: str) -> int:
    conn = pymysql.connect(database=database, **MYSQL_CONNECT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM demo_users")
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def test_fastapi_demo_routes_pressure_traffic_to_shadow_db():
    os.environ["AUTO_REGISTER_APP"] = "false"
    os.environ["ZK_ENABLED"] = "false"
    os.environ["SHADOW_ROUTING"] = "true"
    os.environ["HTTP_SERVER_TRACING"] = "true"
    os.environ["APP_NAME"] = "fastapi-shadow-demo"
    os.environ["DEMO_LOCAL_SHADOW_CONFIG"] = "true"

    from examples.fastapi_mysql_shadow_demo.init_demo_db import main as init_demo_db

    init_demo_db()

    import pylinkagent

    pylinkagent.shutdown()
    pylinkagent.bootstrap()

    demo_module = importlib.import_module("examples.fastapi_mysql_shadow_demo.app")
    demo_module = importlib.reload(demo_module)

    biz_before = _count_rows("pylinkagent_demo_biz")
    shadow_before = _count_rows("pylinkagent_demo_shadow")

    with TestClient(demo_module.app) as client:
        normal_response = client.post("/users", json={"name": "normal-user"})
        pressure_response = client.post(
            "/users",
            headers={"X-Pradar-Cluster-Test": "1"},
            json={"name": "pressure-user"},
        )

    biz_after = _count_rows("pylinkagent_demo_biz")
    shadow_after = _count_rows("pylinkagent_demo_shadow")

    assert normal_response.status_code == 200
    assert pressure_response.status_code == 200
    assert normal_response.json()["database"] == "pylinkagent_demo_biz"
    assert pressure_response.json()["database"] == "pylinkagent_demo_shadow"
    assert biz_after == biz_before + 1
    assert shadow_after == shadow_before + 1

    pylinkagent.shutdown()
