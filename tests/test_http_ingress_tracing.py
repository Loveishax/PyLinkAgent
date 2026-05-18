import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.http_server_interceptor import HTTPServerTracingInterceptor, PressureTrafficDetector
from pylinkagent.pradar import Pradar, PradarSwitcher, get_event_store


def setup_function():
    Pradar.clear()
    PradarSwitcher.reset()
    get_event_store().clear()


def teardown_function():
    Pradar.clear()
    PradarSwitcher.reset()
    get_event_store().clear()


def test_pressure_header_detector_recognizes_supported_headers():
    assert PressureTrafficDetector.is_cluster_test({"x-pradar-cluster-test": "1"}) is True
    assert PressureTrafficDetector.is_cluster_test({"p-pradar-cluster-test": "true"}) is True
    assert PressureTrafficDetector.is_cluster_test({"x-pylinkagent-cluster-test": "yes"}) is True
    assert PressureTrafficDetector.is_cluster_test({"x-pradar-cluster-test": "0"}) is False


def test_wsgi_wrapper_keeps_context_until_response_finishes():
    interceptor = HTTPServerTracingInterceptor(app_name="demo-app")
    observed = {}

    def fake_wsgi_app(app_instance, environ, start_response):
        observed["inside_has_context"] = Pradar.has_context()
        observed["inside_cluster_test"] = Pradar.is_cluster_test()
        start_response("200 OK", [])
        return iter([b"ok"])

    wrapped = interceptor.wrap_wsgi_app(fake_wsgi_app)
    response = wrapped(
        object(),
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/orders",
            "HTTP_X_PRADAR_CLUSTER_TEST": "1",
            "REMOTE_ADDR": "10.0.0.8",
        },
        lambda status, headers, exc_info=None: None,
    )

    assert observed["inside_has_context"] is True
    assert observed["inside_cluster_test"] is True
    assert Pradar.has_context() is True

    assert list(response) == [b"ok"]
    assert Pradar.has_context() is False


def test_asgi_wrapper_creates_and_clears_context():
    interceptor = HTTPServerTracingInterceptor(app_name="demo-app")
    observed = {}

    async def fake_asgi_app(app_instance, scope, receive, send):
        observed["inside_has_context"] = Pradar.has_context()
        observed["inside_cluster_test"] = Pradar.is_cluster_test()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    wrapped = interceptor.wrap_asgi_app(fake_asgi_app)
    sent_messages = []

    async def fake_send(message):
        sent_messages.append(message)

    async def fake_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    asyncio.run(
        wrapped(
            object(),
            {
                "type": "http",
                "method": "POST",
                "path": "/orders",
                "headers": [(b"x-pradar-cluster-test", b"1")],
            },
            fake_receive,
            fake_send,
        )
    )

    assert observed["inside_has_context"] is True
    assert observed["inside_cluster_test"] is True
    assert Pradar.has_context() is False
    assert len(sent_messages) == 2
    recent_span = get_event_store().list_recent(limit=1)[0]
    assert recent_span.invoke_type == "HTTP_SERVER"
    assert recent_span.middleware_name == "HTTP"
    assert recent_span.cluster_test is True
    assert recent_span.request_summary == "POST /orders"
    assert recent_span.result_code == "200"


def test_wsgi_wrapper_records_root_span():
    interceptor = HTTPServerTracingInterceptor(app_name="demo-app")

    def fake_wsgi_app(app_instance, environ, start_response):
        start_response("204 NO CONTENT", [])
        return iter([b""])

    wrapped = interceptor.wrap_wsgi_app(fake_wsgi_app)
    response = wrapped(
        object(),
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/inventory",
            "REMOTE_ADDR": "172.18.0.10",
        },
        lambda status, headers, exc_info=None: None,
    )

    assert list(response) == [b""]

    recent_span = get_event_store().list_recent(limit=1)[0]
    assert recent_span.app_name == "demo-app"
    assert recent_span.invoke_id == "0"
    assert recent_span.remote_ip == "172.18.0.10"
    assert recent_span.request_summary == "GET /inventory"
    assert recent_span.result_code == "204"
    assert recent_span.is_entry is True
    assert recent_span.is_server is True
