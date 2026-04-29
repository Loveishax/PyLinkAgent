import json
import os
import subprocess
import sys

import pymysql


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    script = r"""
import importlib
import json
import os
import sys

sys.path.insert(0, r'D:\soft\agent\LinkAgent-main\PyLinkAgent')

os.environ['AUTO_REGISTER_APP'] = 'false'
os.environ['ZK_ENABLED'] = 'false'
os.environ['SHADOW_ROUTING'] = 'true'
os.environ['HTTP_SERVER_TRACING'] = 'true'
os.environ['APP_NAME'] = 'fastapi-shadow-demo'
os.environ['DEMO_LOCAL_SHADOW_CONFIG'] = 'true'
os.environ['DEMO_LOCAL_CLUSTER_TEST_SWITCH'] = 'true'

from examples.fastapi_mysql_shadow_demo.init_demo_db import main as init_demo_db
from fastapi.testclient import TestClient

init_demo_db()

import pylinkagent

pylinkagent.shutdown()
pylinkagent.bootstrap()

demo_module = importlib.import_module('examples.fastapi_mysql_shadow_demo.app')
demo_module = importlib.reload(demo_module)

result = {}

try:
    with TestClient(demo_module.app) as client:
        result['normal'] = client.post('/users', json={'name': 'normal-user'}).json()
        result['pressure'] = client.post(
            '/users',
            headers={'X-Pradar-Cluster-Test': '1'},
            json={'name': 'pressure-user'},
        ).json()
        result['runtime'] = client.get('/debug/runtime').json()
finally:
    pylinkagent.shutdown()

print(json.dumps(result))
"""

    env = os.environ.copy()
    env["PYTHONPATH"] = PROJECT_ROOT

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )

    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    payload = json.loads(lines[-1])

    biz_after = _count_rows("pylinkagent_demo_biz")
    shadow_after = _count_rows("pylinkagent_demo_shadow")

    assert payload["normal"]["database"] == "pylinkagent_demo_biz"
    assert payload["pressure"]["database"] == "pylinkagent_demo_shadow"
    assert payload["runtime"]["shadow_db_config_count"] >= 1
    assert payload["runtime"]["cluster_test_switch_enabled"] is True
    assert biz_after == 3
    assert shadow_after == 3
