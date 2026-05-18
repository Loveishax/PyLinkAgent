import asyncio

import httpx
import requests

from pylinkagent.pradar import Pradar, get_event_store
from pylinkagent.shadow.http_interceptor import (
    CLUSTER_TEST_HEADER,
    CLUSTER_TEST_VALUE,
    HTTPShadowInterceptor,
)


class _FakeRouter:
    def __init__(self, should_route: bool):
        self._should_route = should_route

    def should_route(self) -> bool:
        return self._should_route


def setup_function():
    Pradar.clear()
    get_event_store().clear()


def teardown_function():
    Pradar.clear()
    get_event_store().clear()


def test_requests_outbound_header_injected(monkeypatch):
    observed = {}

    def fake_request(session, method, url, *args, **kwargs):
        observed["headers"] = dict(kwargs.get("headers") or {})
        return {"ok": True}

    monkeypatch.setattr(requests.Session, "request", fake_request)

    interceptor = HTTPShadowInterceptor(_FakeRouter(True))
    assert interceptor.patch() is True

    try:
        Pradar.start_trace("demo-app", "/upstream", "GET")
        session = requests.Session()
        result = session.request("GET", "http://example.com")
        assert result == {"ok": True}
        assert observed["headers"][CLUSTER_TEST_HEADER] == CLUSTER_TEST_VALUE
        Pradar.end_trace()
        spans = get_event_store().list_recent(limit=2)
        child_span = spans[-2]
        root_span = spans[-1]
        assert child_span.invoke_type == "HTTP_CLIENT"
        assert child_span.middleware_name == "HTTP"
        assert child_span.service_name == "example.com"
        assert child_span.method_name == "GET /"
        assert child_span.result_code == "200"
        assert root_span.invoke_id == "0"
    finally:
        interceptor.unpatch()


def test_httpx_outbound_header_injected(monkeypatch):
    observed = {}

    def fake_send(client, request, *args, **kwargs):
        observed["cluster_header"] = request.headers.get(CLUSTER_TEST_HEADER)
        return httpx.Response(200, request=request, json={"ok": True})

    async def fake_async_send(client, request, *args, **kwargs):
        observed["async_cluster_header"] = request.headers.get(CLUSTER_TEST_HEADER)
        return httpx.Response(200, request=request, json={"ok": True})

    monkeypatch.setattr(httpx.Client, "send", fake_send)
    monkeypatch.setattr(httpx.AsyncClient, "send", fake_async_send)

    interceptor = HTTPShadowInterceptor(_FakeRouter(True))
    assert interceptor.patch() is True

    try:
        Pradar.start_trace("demo-app", "/upstream", "GET")
        client = httpx.Client()
        request = client.build_request("GET", "http://example.com")
        response = client.send(request)
        assert response.status_code == 200
        assert observed["cluster_header"] == CLUSTER_TEST_VALUE

        async def run_async():
            async with httpx.AsyncClient() as async_client:
                async_request = async_client.build_request("GET", "http://example.com")
                async_response = await async_client.send(async_request)
                assert async_response.status_code == 200

        asyncio.run(run_async())
        assert observed["async_cluster_header"] == CLUSTER_TEST_VALUE
        Pradar.end_trace()
        spans = get_event_store().list_recent()
        http_client_spans = [span for span in spans if span.invoke_type == "HTTP_CLIENT"]
        assert len(http_client_spans) == 2
        assert all(span.result_code == "200" for span in http_client_spans)
    finally:
        interceptor.unpatch()


def test_outbound_headers_not_injected_for_normal_traffic(monkeypatch):
    observed = {}

    def fake_request(session, method, url, *args, **kwargs):
        observed["headers"] = dict(kwargs.get("headers") or {})
        return {"ok": True}

    monkeypatch.setattr(requests.Session, "request", fake_request)

    interceptor = HTTPShadowInterceptor(_FakeRouter(False))
    assert interceptor.patch() is True

    try:
        requests.Session().request("GET", "http://example.com")
        assert CLUSTER_TEST_HEADER not in observed["headers"]
    finally:
        interceptor.unpatch()
