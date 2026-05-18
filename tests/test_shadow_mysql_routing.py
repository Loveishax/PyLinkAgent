import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.pradar import Pradar, PradarSwitcher, get_event_store
from pylinkagent.shadow.config_center import ShadowConfigCenter, ShadowDatabaseConfig
from pylinkagent.shadow.mysql_interceptor import MySQLShadowInterceptor
from pylinkagent.shadow.redis_interceptor import RedisShadowInterceptor
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
    get_event_store().clear()
    PradarSwitcher.turn_cluster_test_switch_on()
    Pradar.start_trace("demo-app", "GET /orders", "request")


def _end_cluster_test_trace():
    if Pradar.has_context():
        Pradar.end_trace()
    Pradar.clear()
    PradarSwitcher.reset()
    get_event_store().clear()


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


def test_mysql_interceptor_records_execute_span():
    router = _build_router_with_shadow_db()
    interceptor = MySQLShadowInterceptor(router)

    class FakeCursor:
        def execute(self, sql, *args, **kwargs):
            return {"sql": sql}

    class FakeConnection:
        def cursor(self, *args, **kwargs):
            return FakeCursor()

    def fake_connect(*args, **kwargs):
        return FakeConnection()

    _start_cluster_test_trace()
    try:
        wrapped = interceptor._wrapped_connect(fake_connect)
        connection = wrapped(host="biz-host", port=3306, user="biz_user", password="biz_pwd", db="app")
        result = connection.cursor().execute("select * from orders where id=1")
    finally:
        spans = get_event_store().list_recent()
        _end_cluster_test_trace()

    assert result == {"sql": "select * from orders where id=1"}
    db_spans = [span for span in spans if span.invoke_type == "DB"]
    assert len(db_spans) == 1
    span = db_spans[0]
    assert span.middleware_name == "MYSQL"
    assert span.method_name == "SELECT"
    assert span.service_name == "shadow-host:3307/app_shadow"
    assert "select * from orders" in span.request_summary.lower()
    assert span.result_code == "SUCCESS"


def test_redis_interceptor_records_command_span():
    class _FakeRouter:
        def route_redis(self, host="localhost", port=6379):
            return {"host": "redis-shadow", "port": 6380, "db": 2}

    interceptor = RedisShadowInterceptor(_FakeRouter())

    class FakeRedisBase:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def execute_command(self, *args, **kwargs):
            return {"command": args}

    proxy_cls = interceptor._wrapped_redis_class(FakeRedisBase)

    _start_cluster_test_trace()
    try:
        client = proxy_cls(host="redis-biz", port=6379, db=0)
        result = client.execute_command("GET", "order:1")
        spans = get_event_store().list_recent()
    finally:
        _end_cluster_test_trace()

    assert result == {"command": ("GET", "order:1")}
    cache_spans = [span for span in spans if span.invoke_type == "CACHE"]
    assert len(cache_spans) == 1
    span = cache_spans[0]
    assert span.middleware_name == "REDIS"
    assert span.method_name == "GET"
    assert span.service_name == "redis-shadow:6380/2"
    assert span.request_summary == "GET order:1"
    assert span.result_code == "SUCCESS"
