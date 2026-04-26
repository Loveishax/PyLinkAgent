import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.pradar import Pradar, PradarSwitcher
from pylinkagent.shadow.config_center import ShadowConfigCenter, ShadowDatabaseConfig
from pylinkagent.shadow.mysql_interceptor import MySQLShadowInterceptor
from pylinkagent.shadow.router import ShadowRouter
from pylinkagent.shadow.sqlalchemy_interceptor import SQLAlchemyShadowInterceptor


def _build_router_with_shadow_db() -> ShadowRouter:
    config = ShadowDatabaseConfig.from_dict(
        {
            "dsType": 0,
            "url": "jdbc:mysql://biz-host:3306/app",
            "shadowDbConfig": {
                "datasourceMediator": {
                    "dataSourceBusiness": "biz",
                    "dataSourcePerformanceTest": "shadow",
                },
                "dataSources": [
                    {
                        "id": "biz",
                        "url": "jdbc:mysql://biz-host:3306/app",
                        "username": "biz_user",
                        "password": "biz_pwd",
                    },
                    {
                        "id": "shadow",
                        "url": "jdbc:mysql://shadow-host:3307/app_shadow",
                        "username": "shadow_user",
                        "password": "shadow_pwd",
                    },
                ],
            },
        }
    )
    center = ShadowConfigCenter()
    center.register_db_config(config)
    return ShadowRouter(center)


def _start_cluster_test_trace():
    PradarSwitcher.reset()
    Pradar.clear()
    PradarSwitcher.turn_cluster_test_switch_on()
    Pradar.start_trace("demo-app", "GET /orders", "request")


def _end_cluster_test_trace():
    if Pradar.has_context():
        Pradar.end_trace()
    Pradar.clear()
    PradarSwitcher.reset()


def test_router_returns_shadow_mysql_params_for_cluster_test():
    router = _build_router_with_shadow_db()
    _start_cluster_test_trace()
    try:
        routed = router.route_mysql("jdbc:mysql://biz-host:3306/app", "biz_user", "biz_pwd")
    finally:
        _end_cluster_test_trace()

    assert routed is not None
    assert routed["host"] == "shadow-host"
    assert routed["port"] == 3307
    assert routed["database"] == "app_shadow"
    assert routed["user"] == "shadow_user"
    assert routed["password"] == "shadow_pwd"


def test_mysql_interceptor_rewrites_db_kwargs():
    router = _build_router_with_shadow_db()
    interceptor = MySQLShadowInterceptor(router)
    captured = {}

    def fake_connect(*args, **kwargs):
        captured.update(kwargs)
        return kwargs

    _start_cluster_test_trace()
    try:
        wrapped = interceptor._wrapped_connect(fake_connect)
        wrapped(host="biz-host", port=3306, user="biz_user", password="biz_pwd", db="app")
    finally:
        _end_cluster_test_trace()

    assert captured["host"] == "shadow-host"
    assert captured["port"] == 3307
    assert captured["db"] == "app_shadow"
    assert captured["database"] == "app_shadow"
    assert captured["user"] == "shadow_user"
    assert captured["password"] == "shadow_pwd"


def test_sqlalchemy_interceptor_rewrites_engine_url():
    router = _build_router_with_shadow_db()
    interceptor = SQLAlchemyShadowInterceptor(router)
    captured = {}

    def fake_create_engine(url, *args, **kwargs):
        captured["url"] = str(url)
        return url

    _start_cluster_test_trace()
    try:
        wrapped = interceptor._wrapped_create_engine(fake_create_engine)
        wrapped("mysql+pymysql://biz-host:3306/app")
    finally:
        _end_cluster_test_trace()

    assert captured["url"] == "mysql+pymysql://shadow-host:3307/app_shadow"
