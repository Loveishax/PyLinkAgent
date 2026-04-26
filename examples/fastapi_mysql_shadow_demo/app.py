"""
FastAPI + MySQL shadow-routing demo for PyLinkAgent.

The application code always connects to the business database.
When the agent is mounted and pressure traffic is detected, the MySQL interceptor
reroutes `pymysql.connect()` to the shadow database automatically.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List

import pymysql
from fastapi import FastAPI
from pydantic import BaseModel

from pylinkagent.pradar import PradarSwitcher
from pylinkagent.shadow import ShadowDatabaseConfig, get_config_center


logger = logging.getLogger(__name__)


BUSINESS_DB = {
    "host": os.getenv("DEMO_MYSQL_HOST", "localhost"),
    "port": int(os.getenv("DEMO_MYSQL_PORT", "3306")),
    "user": os.getenv("DEMO_MYSQL_USER", "root"),
    "password": os.getenv("DEMO_MYSQL_PASSWORD", "123456"),
    "database": os.getenv("DEMO_BIZ_DB", "pylinkagent_demo_biz"),
    "charset": "utf8mb4",
    "autocommit": True,
}

SHADOW_DB_NAME = os.getenv("DEMO_SHADOW_DB", "pylinkagent_demo_shadow")

BUSINESS_JDBC_URL = (
    f"jdbc:mysql://{BUSINESS_DB['host']}:{BUSINESS_DB['port']}/{BUSINESS_DB['database']}"
)
SHADOW_JDBC_URL = (
    f"jdbc:mysql://{BUSINESS_DB['host']}:{BUSINESS_DB['port']}/{SHADOW_DB_NAME}"
)

LOCAL_SHADOW_CONFIG_ENABLED = os.getenv("DEMO_LOCAL_SHADOW_CONFIG", "true").lower() == "true"
LOCAL_CLUSTER_TEST_SWITCH_ENABLED = (
    os.getenv("DEMO_LOCAL_CLUSTER_TEST_SWITCH", "true").lower() == "true"
)


class CreateUserRequest(BaseModel):
    name: str


def _register_local_shadow_config() -> None:
    """Register a local shadow DB config for offline verification."""
    shadow_config = ShadowDatabaseConfig(
        datasource_name="demo-mysql",
        url=BUSINESS_JDBC_URL,
        username=BUSINESS_DB["user"],
        password=BUSINESS_DB["password"],
        shadow_url=SHADOW_JDBC_URL,
        shadow_username=BUSINESS_DB["user"],
        shadow_password=BUSINESS_DB["password"],
        ds_type=0,
        enabled=True,
    )
    get_config_center().register_db_config(shadow_config)
    logger.info(
        "Registered local demo shadow config: %s -> %s",
        BUSINESS_JDBC_URL,
        SHADOW_JDBC_URL,
    )


def _enable_local_cluster_test_switch() -> None:
    """Enable the global pressure switch for offline demo verification."""
    PradarSwitcher.clear_cluster_test_unable()
    PradarSwitcher.turn_cluster_test_switch_on()
    logger.info("Enabled local demo cluster-test switch")


def _startup() -> None:
    if LOCAL_SHADOW_CONFIG_ENABLED:
        _register_local_shadow_config()
    if LOCAL_CLUSTER_TEST_SWITCH_ENABLED:
        _enable_local_cluster_test_switch()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _startup()
    yield


app = FastAPI(
    title="PyLinkAgent FastAPI MySQL Demo",
    version="1.0.0",
    description="Business writes use the business DB config only; the agent reroutes pressure traffic.",
    lifespan=lifespan,
)


def _get_business_connection():
    """The demo application only knows the business DB config."""
    return pymysql.connect(**BUSINESS_DB)


def _fetch_db_name() -> str:
    conn = _get_business_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            return cur.fetchone()[0]
    finally:
        conn.close()


def _fetch_users() -> List[Dict]:
    conn = _get_business_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id, name, note FROM demo_users ORDER BY id")
            return list(cur.fetchall())
    finally:
        conn.close()


def _insert_user(name: str, note: str) -> Dict:
    conn = _get_business_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "INSERT INTO demo_users(name, note) VALUES (%s, %s)",
                (name, note),
            )
            inserted_id = cur.lastrowid
            cur.execute(
                "SELECT id, name, note FROM demo_users WHERE id = %s",
                (inserted_id,),
            )
            row = cur.fetchone()
        return row
    finally:
        conn.close()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "local_shadow_config": LOCAL_SHADOW_CONFIG_ENABLED,
        "local_cluster_test_switch": LOCAL_CLUSTER_TEST_SWITCH_ENABLED,
        "business_jdbc_url": BUSINESS_JDBC_URL,
        "shadow_jdbc_url": SHADOW_JDBC_URL,
    }


@app.get("/users")
def list_users():
    return {
        "database": _fetch_db_name(),
        "items": _fetch_users(),
    }


@app.post("/users")
def create_user(payload: CreateUserRequest):
    row = _insert_user(payload.name, "written-by-fastapi-demo")
    return {
        "database": _fetch_db_name(),
        "item": row,
    }


@app.get("/debug/config")
def debug_config():
    return {
        "business_db": BUSINESS_DB["database"],
        "shadow_db": SHADOW_DB_NAME,
        "local_shadow_config": LOCAL_SHADOW_CONFIG_ENABLED,
        "local_cluster_test_switch": LOCAL_CLUSTER_TEST_SWITCH_ENABLED,
        "business_jdbc_url": BUSINESS_JDBC_URL,
        "shadow_jdbc_url": SHADOW_JDBC_URL,
    }
