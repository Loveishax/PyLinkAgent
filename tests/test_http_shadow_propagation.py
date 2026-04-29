import asyncio

import httpx
import requests

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


def test_requests_outbound_header_injected(monkeypatch):
    observed = {}

    def fake_request(session, method, url, *args, **kwargs):
        observed["headers"] = dict(kwargs.get("headers") or {})
        return {"ok": True}

    monkeypatch.setattr(requests.Session, "request", fake_request)

    interceptor = HTTPShadowInterceptor(_FakeRouter(True))
    assert interceptor.patch() is True

    try:
        session = requests.Session()
        result = session.request("GET", "http://example.com")
        assert result == {"ok": True}
        assert observed["headers"][CLUSTER_TEST_HEADER] == CLUSTER_TEST_VALUE
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
