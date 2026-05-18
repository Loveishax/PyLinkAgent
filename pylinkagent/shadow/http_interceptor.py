"""
HTTP client shadow routing interceptor.
"""

import logging
from typing import Any, Dict, Tuple
from urllib.parse import urlsplit

from ..pradar import Pradar

try:
    import wrapt

    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False


logger = logging.getLogger(__name__)

CLUSTER_TEST_HEADER = "X-Pradar-Cluster-Test"
CLUSTER_TEST_VALUE = "1"


class HTTPShadowInterceptor:
    """Inject pressure headers into outbound HTTP traffic."""

    def __init__(self, router):
        self.router = router
        self._patched = False
        self._original_requests_request = None
        self._original_httpx_send = None
        self._original_httpx_async_send = None

    def patch(self) -> bool:
        if self._patched:
            return True
        if not WRAPT_AVAILABLE:
            logger.warning("wrapt unavailable, skip HTTP shadow interceptor")
            return False

        success = False
        try:
            self._patch_requests()
            success = True
        except Exception as exc:
            logger.debug("Patch requests failed: %s", exc)

        try:
            self._patch_httpx()
            success = True
        except Exception as exc:
            logger.debug("Patch httpx failed: %s", exc)

        if success:
            self._patched = True
            logger.info("HTTP shadow interceptor enabled")
        return success

    def unpatch(self) -> None:
        if not self._patched:
            return

        try:
            if self._original_requests_request:
                import requests

                requests.Session.request = self._original_requests_request
            if self._original_httpx_send or self._original_httpx_async_send:
                import httpx

                if self._original_httpx_send:
                    httpx.Client.send = self._original_httpx_send
                if self._original_httpx_async_send:
                    httpx.AsyncClient.send = self._original_httpx_async_send
        except Exception as exc:
            logger.debug("Restore HTTP shadow interceptor failed: %s", exc)

        self._patched = False
        logger.info("HTTP shadow interceptor disabled")

    def _patch_requests(self) -> None:
        import functools
        import requests

        self._original_requests_request = requests.Session.request

        @functools.wraps(self._original_requests_request)
        def wrapped_request(session, method, url, *args, **kwargs):
            headers = self._inject_cluster_test_header(dict(kwargs.get("headers") or {}), url)
            if headers:
                kwargs["headers"] = headers

            span_ctx = self._start_http_client_span(method, url)
            try:
                response = self._original_requests_request(session, method, url, *args, **kwargs)
                if span_ctx:
                    Pradar.set_result_code(getattr(response, "status_code", "200"))
                    Pradar.set_response_summary(
                        f"status={getattr(response, 'status_code', 200)}"
                    )
                return response
            except Exception as exc:
                if span_ctx:
                    Pradar.set_error(str(exc))
                    Pradar.set_result_code("EXCEPTION")
                raise
            finally:
                self._finish_http_client_span(span_ctx)

        requests.Session.request = wrapped_request

    def _patch_httpx(self) -> None:
        import functools
        import httpx

        self._original_httpx_send = httpx.Client.send
        self._original_httpx_async_send = httpx.AsyncClient.send

        @functools.wraps(self._original_httpx_send)
        def wrapped_send(client, request, *args, **kwargs):
            if self.router.should_route():
                request.headers[CLUSTER_TEST_HEADER] = CLUSTER_TEST_VALUE
                logger.debug("Injected pressure header into httpx: %s", request.url)

            span_ctx = self._start_http_client_span(request.method, str(request.url))
            try:
                response = self._original_httpx_send(client, request, *args, **kwargs)
                if span_ctx:
                    Pradar.set_result_code(getattr(response, "status_code", "200"))
                    Pradar.set_response_summary(
                        f"status={getattr(response, 'status_code', 200)}"
                    )
                return response
            except Exception as exc:
                if span_ctx:
                    Pradar.set_error(str(exc))
                    Pradar.set_result_code("EXCEPTION")
                raise
            finally:
                self._finish_http_client_span(span_ctx)

        @functools.wraps(self._original_httpx_async_send)
        async def wrapped_async_send(client, request, *args, **kwargs):
            if self.router.should_route():
                request.headers[CLUSTER_TEST_HEADER] = CLUSTER_TEST_VALUE
            span_ctx = self._start_http_client_span(request.method, str(request.url))
            try:
                response = await self._original_httpx_async_send(client, request, *args, **kwargs)
                if span_ctx:
                    Pradar.set_result_code(getattr(response, "status_code", "200"))
                    Pradar.set_response_summary(
                        f"status={getattr(response, 'status_code', 200)}"
                    )
                return response
            except Exception as exc:
                if span_ctx:
                    Pradar.set_error(str(exc))
                    Pradar.set_result_code("EXCEPTION")
                raise
            finally:
                self._finish_http_client_span(span_ctx)

        httpx.Client.send = wrapped_send
        httpx.AsyncClient.send = wrapped_async_send

    def _inject_cluster_test_header(self, headers: Dict[str, Any], url: str) -> Dict[str, Any]:
        if self.router.should_route():
            headers[CLUSTER_TEST_HEADER] = CLUSTER_TEST_VALUE
            logger.debug("Injected pressure header into outbound HTTP: %s", url)
        return headers

    def _start_http_client_span(self, method: str, url: str):
        if not Pradar.has_context():
            return None

        service_name, method_name, remote_ip, port = self._parse_request_target(method, url)
        span_ctx = Pradar.start_child_span(
            service_name=service_name,
            method_name=method_name,
            middleware_name="HTTP",
            invoke_type="HTTP_CLIENT",
            remote_ip=remote_ip,
            port=port,
            up_app_name=service_name,
            is_server=False,
        )
        if span_ctx:
            Pradar.set_request_summary(url)
        return span_ctx

    @staticmethod
    def _finish_http_client_span(span_ctx) -> None:
        if span_ctx and Pradar.get_context() is span_ctx:
            Pradar.end_trace()

    @staticmethod
    def _parse_request_target(method: str, url: str) -> Tuple[str, str, str, int]:
        parsed = urlsplit(url)
        host = parsed.hostname or parsed.netloc or "unknown-host"
        path = parsed.path or "/"
        port = int(parsed.port or (443 if parsed.scheme == "https" else 80))
        return host, f"{str(method).upper()} {path}", host, port
