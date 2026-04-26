import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.http_server_interceptor import HTTPServerTracingInterceptor, PressureTrafficDetector
from pylinkagent.pradar import Pradar, PradarSwitcher


def setup_function():
    Pradar.clear()
    PradarSwitcher.reset()


def teardown_function():
    Pradar.clear()
    PradarSwitcher.reset()


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
